from __future__ import annotations

import shutil
from pathlib import Path

import psutil

_GIB = 1024**3


def _gb(value: int | float) -> float:
    return round(float(value) / _GIB, 2)


def _tool_volume_snapshot(model_root: str) -> dict:
    path = Path(model_root).resolve()
    usage = shutil.disk_usage(path)
    anchor = path.anchor or str(path)
    return {
        "path": str(path),
        "volume": anchor.rstrip("\\/") or anchor,
        "total_bytes": int(usage.total),
        "used_bytes": int(usage.used),
        "free_bytes": int(usage.free),
        "total_gb": _gb(usage.total),
        "used_gb": _gb(usage.used),
        "free_gb": _gb(usage.free),
        "display_unit": "GiB",
        "source": "native-windows-tool-volume",
    }


def _freetoken_memory_snapshot(model_root: str) -> dict:
    root = Path(model_root).resolve().parent
    pid_path = root / "state" / "freetoken.pid"
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        parent = psutil.Process(pid)
        processes = [parent, *parent.children(recursive=True)]
    except (OSError, ValueError, psutil.Error):
        return {"running": False}

    rss = 0
    sampled = 0
    for process in processes:
        try:
            rss += int(process.memory_info().rss)
            sampled += 1
        except psutil.Error:
            pass
    if sampled == 0:
        return {"running": False}
    return {
        "running": True,
        "pid": pid,
        "process_count": sampled,
        "rss_gb": _gb(rss),
    }


def system_snapshot(
    model_root: str,
    *,
    force_host_storage_refresh: bool = False,
) -> dict:
    del force_host_storage_refresh
    vm = psutil.virtual_memory()
    volume = _tool_volume_snapshot(model_root)
    runtime_filesystem = dict(volume)
    runtime_filesystem["source"] = "native-windows-filesystem"

    return {
        "platform": "windows",
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_total_gb": round(vm.total / _GIB, 2),
        "ram_used_gb": round(vm.used / _GIB, 2),
        "ram_available_gb": round(vm.available / _GIB, 2),
        "ram_percent": vm.percent,
        "freetoken_memory": _freetoken_memory_snapshot(model_root),
        "host_storage": dict(volume),
        "wsl_virtual_disk": runtime_filesystem,
        "model_disk": dict(volume),
    }
