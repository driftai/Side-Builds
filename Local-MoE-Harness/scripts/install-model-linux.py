#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.model_registry import ModelRegistry, ModelRegistryError  # noqa: E402
from app.services.system_metrics import system_snapshot  # noqa: E402


def fail(message: str) -> None:
    print(f"[Model Install] ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


HF_PYTHON = ROOT / ".venvs" / "freetoken" / "bin" / "python"
GB = 1_000_000_000
GIB = 1024**3


@dataclass(frozen=True)
class StorageSnapshot:
    wsl_free_bytes: int
    host_free_bytes: int
    vhd_file_bytes: int | None


def format_storage_size(value: int) -> str:
    """Show both unit systems so host and guest figures stay comparable."""
    return f"{value / GB:.2f} GB ({value / GIB:.2f} GiB)"


def storage_snapshot(path: Path) -> StorageSnapshot:
    usage = shutil.disk_usage(path)
    metrics = system_snapshot(str(path), force_host_storage_refresh=True)
    host = metrics.get("host_storage") or {}
    host_free = host.get("free_bytes")
    if not isinstance(host_free, int):
        # Compatibility with a metrics provider predating exact byte fields.
        # The legacy *_gb fields contain binary GiB values despite their name.
        legacy_free_gib = host.get("free_gb")
        if isinstance(legacy_free_gib, (int, float)):
            host_free = int(float(legacy_free_gib) * GIB)
    if not isinstance(host_free, int) or host_free < 0:
        raise RuntimeError("Windows backing-volume free space could not be verified.")
    vhd_file_bytes = host.get("vhd_file_bytes")
    if not isinstance(vhd_file_bytes, int) or vhd_file_bytes < 0:
        vhd_file_bytes = None
    return StorageSnapshot(
        wsl_free_bytes=int(usage.free),
        host_free_bytes=host_free,
        vhd_file_bytes=vhd_file_bytes,
    )


def existing_selected_bytes(local_dir: Path, filenames: list[str]) -> int:
    total = 0
    for filename in filenames:
        path = local_dir / filename
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def storage_accounting(
    before: StorageSnapshot,
    after: StorageSnapshot,
    expected_new_bytes: int,
) -> tuple[str, bool]:
    wsl_used_delta = before.wsl_free_bytes - after.wsl_free_bytes
    host_free_delta = after.host_free_bytes - before.host_free_bytes
    parts = [f"WSL logical used {wsl_used_delta / GIB:+.2f} GiB"]
    if before.vhd_file_bytes is not None and after.vhd_file_bytes is not None:
        parts.append(
            f"VHDX file {(after.vhd_file_bytes - before.vhd_file_bytes) / GIB:+.2f} GiB"
        )
    parts.append(f"Windows free {host_free_delta / GIB:+.2f} GiB")

    tolerance = max(GIB, int(max(expected_new_bytes, 0) * 0.10))
    amplified = wsl_used_delta > expected_new_bytes + tolerance
    return "; ".join(parts) + ".", amplified


def selected_remote_size(repo_id: str, revision: str, filenames: list[str]) -> int:
    helper = """
import json, sys
from huggingface_hub import HfApi
repo_id, revision, raw_files = sys.argv[1:4]
filenames = json.loads(raw_files)
info = HfApi().model_info(repo_id, revision=revision, files_metadata=True)
sizes = {item.rfilename: item.size for item in info.siblings if item.size is not None}
missing = [name for name in filenames if name not in sizes]
if missing:
    raise RuntimeError('missing metadata: ' + ', '.join(missing))
print(sum(int(sizes[name]) for name in filenames))
"""
    proc = subprocess.run(
        [str(HF_PYTHON), "-c", helper, repo_id, revision, json.dumps(filenames)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip())
    return int(proc.stdout.strip())


def download_file(repo_id: str, revision: str, filename: str, local_dir: Path) -> None:
    helper = """
import sys
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id=sys.argv[1], filename=sys.argv[2], revision=sys.argv[3], local_dir=sys.argv[4]
)
"""
    proc = subprocess.run(
        [
            str(HF_PYTHON),
            "-c",
            helper,
            repo_id,
            filename,
            revision,
            str(local_dir),
        ],
        check=False,
    )
    if proc.returncode != 0:
        fail(f"download failed for {filename} (exit {proc.returncode}).")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Explicitly install one trusted registry model checkpoint."
    )
    parser.add_argument("model_id")
    parser.add_argument(
        "--dry-run", action="store_true", help="Check manifest and disk budget only."
    )
    args = parser.parse_args()

    try:
        registry = ModelRegistry(ROOT)
        record = registry.require(args.model_id)
    except ModelRegistryError as exc:
        fail(str(exc))

    download = record.data.get("download")
    if not download:
        fail(f"{record.id} is not approved for installation on this machine.")
    revision = record.data.get("revision")
    if not isinstance(revision, str) or len(revision) != 40:
        fail(f"{record.id} does not have an immutable 40-character revision pin.")

    filenames = list(download["files"])
    try:
        remote_bytes = selected_remote_size(
            str(record.data["hf_repo"]), revision, filenames
        )
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"could not read pinned Hugging Face metadata: {exc}")

    declared_bytes = int(download["expected_bytes"])
    tolerance = max(50_000_000, int(declared_bytes * 0.03))
    if abs(remote_bytes - declared_bytes) > tolerance:
        fail(
            "pinned checkpoint size differs from the registry estimate: "
            f"registry={format_storage_size(declared_bytes)}, "
            f"remote={format_storage_size(remote_bytes)}"
        )

    record.local_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        before = storage_snapshot(record.local_path.parent)
    except RuntimeError as exc:
        fail(str(exc))
    reserve_bytes = int(registry.disk_reserve_gb * GB)
    required_free = remote_bytes + reserve_bytes
    if before.wsl_free_bytes < required_free:
        fail(
            f"WSL storage needs {format_storage_size(required_free)} including reserve; "
            f"only {format_storage_size(before.wsl_free_bytes)} is free."
        )
    if before.host_free_bytes < required_free:
        fail(
            "Windows backing volume needs "
            f"{format_storage_size(required_free)} including reserve; "
            f"only {format_storage_size(before.host_free_bytes)} is free."
        )

    if args.dry_run:
        print(
            f"[Model Install] SAFE: {record.id} payload {format_storage_size(remote_bytes)}; "
            f"host free {format_storage_size(before.host_free_bytes)}; "
            f"WSL free {format_storage_size(before.wsl_free_bytes)}; "
            f"reserve {format_storage_size(reserve_bytes)}."
        )
        return 0

    existing_bytes = existing_selected_bytes(record.local_path, filenames)
    expected_new_bytes = max(0, remote_bytes - min(remote_bytes, existing_bytes))
    record.local_path.mkdir(parents=True, exist_ok=True)
    print(
        f"[Model Install] Downloading {len(filenames)} pinned files "
        f"({format_storage_size(remote_bytes)}) for {record.id}..."
    )
    for filename in filenames:
        download_file(
            str(record.data["hf_repo"]),
            revision,
            filename,
            record.local_path,
        )

    if not registry.is_installed(record):
        fail("download finished but required checkpoint files are incomplete.")
    try:
        after = storage_snapshot(record.local_path.parent)
        accounting, amplified = storage_accounting(
            before, after, expected_new_bytes
        )
        print(f"[Model Install] Storage accounting: {accounting}")
        if amplified:
            print(
                "[Model Install] WARNING: Unexpected guest-storage amplification "
                "detected; inspect model-local cache, Hugging Face cache, and temp paths."
            )
    except RuntimeError as exc:
        print(f"[Model Install] WARNING: Post-install storage accounting unavailable: {exc}")
    print(
        f"[Model Install] INSTALLED: {record.id} at {record.local_path} "
        f"({format_storage_size(remote_bytes)} pinned payload)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
