from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import psutil

_GIB = 1024**3
_HOST_STORAGE_CACHE_TTL_SECONDS = 30.0
_HOST_STORAGE_ERROR_TTL_SECONDS = 3.0
_host_storage_cache: dict | None = None
_host_storage_cache_at = 0.0
_WSL_INTEROP_DIR = "/run/WSL"
_WSL_INTEROP_PATTERN = re.compile(r"^(\d+)_interop$")


def _is_process_alive(pid: int, *, proc_dir: str = "/proc") -> bool:
    """Check if process exists and is not a dead WSL session relay."""
    pid_dir = os.path.join(proc_dir, str(pid))
    if not os.path.exists(pid_dir):
        return False
    status_file = os.path.join(pid_dir, "status")
    if os.path.isfile(status_file):
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("Name:"):
                        name = line.split(":", 1)[1].strip()
                        match = re.match(r"^Relay\((\d+)\)$", name)
                        if match:
                            target_pid = match.group(1)
                            return os.path.exists(os.path.join(proc_dir, target_pid))
                        break
        except OSError:
            return False
    return True


def _is_usable_wsl_interop_socket(
    path: str | None,
    *,
    proc_dir: str = "/proc",
) -> bool:
    """Return True if path points to an existing interop socket with a live process."""
    if not path or not isinstance(path, str):
        return False
    if not os.path.exists(path):
        return False
    filename = os.path.basename(path)
    match = _WSL_INTEROP_PATTERN.match(filename)
    if not match:
        return False
    pid = int(match.group(1))
    if _is_process_alive(pid, proc_dir=proc_dir):
        return True
    if os.path.islink(path):
        try:
            target_base = os.path.basename(os.path.realpath(path))
            target_match = _WSL_INTEROP_PATTERN.match(target_base)
            if target_match:
                return _is_process_alive(int(target_match.group(1)), proc_dir=proc_dir)
        except OSError:
            pass
    return False


def _discover_wsl_interop_socket(
    *,
    interop_dir: str = _WSL_INTEROP_DIR,
    proc_dir: str = "/proc",
) -> str | None:
    """Defensively find the best live WSL interop socket in interop_dir."""
    if not os.path.isdir(interop_dir):
        return None

    try:
        entries = os.listdir(interop_dir)
    except OSError:
        return None

    candidates: list[tuple[bool, int, int, str]] = []
    for entry in entries:
        match = _WSL_INTEROP_PATTERN.match(entry)
        if not match:
            continue
        pid = int(match.group(1))
        full_path = os.path.join(interop_dir, entry)
        if not os.path.exists(full_path):
            continue

        proc_alive = _is_process_alive(pid, proc_dir=proc_dir)
        if not proc_alive and os.path.islink(full_path):
            try:
                target_base = os.path.basename(os.path.realpath(full_path))
                target_match = _WSL_INTEROP_PATTERN.match(target_base)
                if target_match:
                    proc_alive = _is_process_alive(int(target_match.group(1)), proc_dir=proc_dir)
            except OSError:
                pass

        # Ranking criteria:
        # 1. proc_alive: live process (True) strictly outranks dead processes (False)
        # 2. preference: PID 1 (score 2), PID 2 (score 1), others (score 0)
        # 3. tie-breaker: smaller PID first (-pid)
        pref = 2 if pid == 1 else (1 if pid == 2 else 0)
        candidates.append((proc_alive, pref, -pid, full_path))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    best_alive, _, _, best_path = candidates[0]
    if not best_alive:
        return None
    return best_path


def _resolve_wsl_interop_environment(
    env: dict[str, str] | None = None,
    *,
    interop_dir: str = _WSL_INTEROP_DIR,
    proc_dir: str = "/proc",
) -> dict[str, str]:
    """Resolve a valid WSL_INTEROP environment for Windows host process invocation."""
    resolved = dict(os.environ if env is None else env)
    inherited = resolved.get("WSL_INTEROP")
    if _is_usable_wsl_interop_socket(inherited, proc_dir=proc_dir):
        return resolved

    replacement = _discover_wsl_interop_socket(
        interop_dir=interop_dir,
        proc_dir=proc_dir,
    )
    if replacement is not None:
        resolved["WSL_INTEROP"] = replacement
    return resolved


def _gb(value: int | float) -> float:
    return round(float(value) / _GIB, 2)


def _wsl_virtual_disk_snapshot(model_root: str) -> dict:
    """Report the Linux-visible filesystem geometry for the model path.

    Under WSL2 this is the ext4 VHD's virtual filesystem capacity, not the
    amount of physical space available on the Windows volume that stores the
    VHDX. Keep it as a diagnostic, but never present it as host free space.
    """
    root = Path(model_root)
    probe = root if root.exists() else root.parent
    try:
        usage = shutil.disk_usage(probe)
        return {
            "path": str(root),
            "total_bytes": int(usage.total),
            "used_bytes": int(usage.used),
            "free_bytes": int(usage.free),
            "total_gb": _gb(usage.total),
            "used_gb": _gb(usage.used),
            "free_gb": _gb(usage.free),
            "display_unit": "GiB",
            "source": "wsl-virtual-filesystem",
        }
    except Exception as exc:
        return {
            "path": str(root),
            "source": "wsl-virtual-filesystem",
            "error": str(exc),
        }


def _powershell_host_storage(
    distro_name: str,
    timeout_seconds: float = 6.0,
    *,
    env: dict[str, str] | None = None,
) -> dict:
    """Resolve the Windows volume that physically stores this WSL distro VHDX."""
    distro_b64 = base64.b64encode(distro_name.encode("utf-8")).decode("ascii")
    script = rf"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$distro = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{distro_b64}'))
$key = Get-ChildItem -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' |
    Where-Object {{ $_.GetValue('DistributionName') -eq $distro }} |
    Select-Object -First 1
if (-not $key) {{ throw "WSL registry entry not found for distro '$distro'." }}
$baseRaw = [string]$key.GetValue('BasePath')
if ([string]::IsNullOrWhiteSpace($baseRaw)) {{ throw "WSL BasePath is empty for distro '$distro'." }}
$base = [Environment]::ExpandEnvironmentVariables($baseRaw)
# Import-in-place registrations use the Win32 extended-path prefix. PowerShell's
# filesystem provider cannot Join-Path that form reliably, so normalize it before
# resolving the backing drive and VHDX.
if ($base.StartsWith('\\?\', [System.StringComparison]::Ordinal)) {{
    $base = $base.Substring(4)
}}
if ($base -notmatch '^([A-Za-z]:)') {{
    throw "Could not resolve a Windows drive from WSL BasePath '$base'."
}}
$volume = $Matches[1]
$drive = [System.IO.DriveInfo]::new("$volume\")
$vhd = Join-Path $base 'ext4.vhdx'
if (-not (Test-Path -LiteralPath $vhd)) {{
    $candidate = Get-ChildItem -LiteralPath $base -Filter '*.vhdx' -File -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($candidate) {{ $vhd = $candidate.FullName }}
}}
$vhdBytes = $null
if (Test-Path -LiteralPath $vhd) {{
    $vhdBytes = (Get-Item -LiteralPath $vhd -Force).Length
}}
[pscustomobject]@{{
    distro = $distro
    base_path = $base
    vhd_path = $vhd
    volume = $volume
    total_bytes = [int64]$drive.TotalSize
    free_bytes = [int64]$drive.AvailableFreeSpace
    vhd_file_bytes = if ($null -eq $vhdBytes) {{ $null }} else {{ [int64]$vhdBytes }}
}} | ConvertTo-Json -Compress
"""

    proc_env = _resolve_wsl_interop_environment(env)

    proc = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=max(0.5, float(timeout_seconds)),
        check=False,
        env=proc_env,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "PowerShell host-storage query failed.").strip()
        raise RuntimeError(detail)

    raw = proc.stdout.strip()
    if not raw:
        raise RuntimeError("PowerShell host-storage query returned no data.")
    data = json.loads(raw)

    total_bytes = int(data["total_bytes"])
    free_bytes = int(data["free_bytes"])
    if total_bytes <= 0 or free_bytes < 0 or free_bytes > total_bytes:
        raise ValueError("PowerShell returned invalid Windows drive capacity values.")

    result = {
        "volume": str(data.get("volume") or "").rstrip("\\"),
        "total_bytes": total_bytes,
        "used_bytes": total_bytes - free_bytes,
        "free_bytes": free_bytes,
        "total_gb": _gb(total_bytes),
        "used_gb": _gb(total_bytes - free_bytes),
        "free_gb": _gb(free_bytes),
        "display_unit": "GiB",
        "source": "windows-wsl-backing-volume",
        "wsl_distro": str(data.get("distro") or distro_name),
        "base_path": str(data.get("base_path") or ""),
        "vhd_path": str(data.get("vhd_path") or ""),
    }
    vhd_file_bytes = data.get("vhd_file_bytes")
    if vhd_file_bytes is not None:
        result["vhd_file_bytes"] = int(vhd_file_bytes)
        result["vhd_file_gb"] = _gb(int(vhd_file_bytes))
    return result


def _short_error_cache_timestamp(now: float) -> float:
    """Back-date a cache entry so normal TTL logic retries it after the error TTL."""
    return now - (_HOST_STORAGE_CACHE_TTL_SECONDS - _HOST_STORAGE_ERROR_TTL_SECONDS)


def _windows_host_storage_snapshot(*, force_refresh: bool = False) -> dict:
    """Return cached Windows backing-volume capacity for the active WSL distro."""
    global _host_storage_cache, _host_storage_cache_at

    now = time.monotonic()
    if (
        not force_refresh
        and _host_storage_cache is not None
        and now - _host_storage_cache_at < _HOST_STORAGE_CACHE_TTL_SECONDS
    ):
        return dict(_host_storage_cache)

    distro_name = os.environ.get("WSL_DISTRO_NAME", "").strip()
    if not distro_name:
        snapshot = {
            "source": "windows-wsl-backing-volume",
            "error": "WSL_DISTRO_NAME is unavailable; Windows backing volume could not be resolved.",
        }
        _host_storage_cache = dict(snapshot)
        _host_storage_cache_at = _short_error_cache_timestamp(now)
        return dict(snapshot)

    try:
        snapshot = _powershell_host_storage(distro_name)
        _host_storage_cache = dict(snapshot)
        _host_storage_cache_at = now
        return dict(snapshot)
    except Exception as exc:
        if _host_storage_cache is not None and "free_gb" in _host_storage_cache:
            # Keep the last known-good capacity visible, but back off repeated
            # PowerShell interop attempts for the short error TTL. Without this,
            # every /api/status poll after cache expiry can pay the full subprocess
            # timeout while Windows interop is temporarily unhealthy.
            snapshot = dict(_host_storage_cache)
            snapshot["stale"] = True
            snapshot["refresh_error"] = str(exc)
            _host_storage_cache = dict(snapshot)
            _host_storage_cache_at = _short_error_cache_timestamp(now)
            return dict(snapshot)
        snapshot = {
            "source": "windows-wsl-backing-volume",
            "wsl_distro": distro_name,
            "error": str(exc),
        }
        _host_storage_cache = dict(snapshot)
        _host_storage_cache_at = _short_error_cache_timestamp(now)
        return dict(snapshot)


def _freetoken_memory_snapshot(model_root: str) -> dict:
    """Read the managed FreeToken process footprint without invoking a new tool."""
    pid_path = Path(model_root).resolve().parent / "state" / "freetoken.pid"
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        process = psutil.Process(pid)
        pids = [pid, *(child.pid for child in process.children(recursive=True))]
    except (OSError, ValueError, psutil.Error):
        return {"running": False}

    values = {key: 0 for key in ("VmRSS", "Pss", "RssAnon", "RssFile", "RssShmem")}
    sampled_pids = 0
    for process_pid in pids:
        try:
            status_lines = (Path("/proc") / str(process_pid) / "status").read_text(
                encoding="utf-8"
            ).splitlines()
        except OSError:
            continue
        sampled_pids += 1
        for line in status_lines:
            key, separator, raw = line.partition(":")
            if separator and key in values:
                try:
                    values[key] += int(raw.strip().split()[0]) * 1024
                except (ValueError, IndexError):
                    pass
        try:
            rollup = (Path("/proc") / str(process_pid) / "smaps_rollup").read_text(
                encoding="utf-8"
            )
            for line in rollup.splitlines():
                if line.startswith("Pss:"):
                    values["Pss"] += int(line.split()[1]) * 1024
                    break
        except (OSError, ValueError, IndexError):
            pass

    if sampled_pids == 0:
        return {"running": False}
    result = {"running": True, "pid": pid, "process_count": sampled_pids}
    key_map = {
        "VmRSS": "rss_gb",
        "Pss": "pss_gb",
        "RssAnon": "rss_anon_gb",
        "RssFile": "rss_file_gb",
        "RssShmem": "rss_shmem_gb",
    }
    for source, target in key_map.items():
        if values[source] > 0:
            result[target] = _gb(values[source])
    return result


def system_snapshot(
    model_root: str,
    *,
    force_host_storage_refresh: bool = False,
) -> dict:
    vm = psutil.virtual_memory()
    wsl_virtual_disk = _wsl_virtual_disk_snapshot(model_root)
    host_storage = _windows_host_storage_snapshot(
        force_refresh=force_host_storage_refresh
    )

    # Backward-compatible key used by the current browser UI. It now aliases
    # the real Windows backing volume instead of the misleading WSL VHD maximum.
    # If host telemetry is unavailable, leave free_gb absent so the UI shows
    # Unavailable rather than falling back to a false physical-capacity number.
    model_disk = dict(host_storage)
    model_disk.setdefault("path", host_storage.get("volume", ""))

    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_total_gb": round(vm.total / _GIB, 2),
        "ram_used_gb": round(vm.used / _GIB, 2),
        "ram_available_gb": round(vm.available / _GIB, 2),
        "ram_percent": vm.percent,
        "freetoken_memory": _freetoken_memory_snapshot(model_root),
        "host_storage": host_storage,
        "wsl_virtual_disk": wsl_virtual_disk,
        "model_disk": model_disk,
    }
