#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.model_registry import ModelRegistry, ModelRegistryError  # noqa: E402

GB = 1_000_000_000
GIB = 1024**3
HF_PYTHON = ROOT / ".venvs" / "freetoken" / "Scripts" / "python.exe"


def format_storage_size(value: int) -> str:
    """Show both unit systems so platform storage figures remain comparable."""
    return f"{value / GB:.2f} GB ({value / GIB:.2f} GiB)"


def fail(message: str) -> None:
    print(f"[Model Install] ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def local_env() -> dict[str, str]:
    cache = ROOT / ".cache"
    appdata = cache / "windows" / "AppData"
    localappdata = cache / "windows" / "LocalAppData"
    temp = ROOT / ".tmp"
    for path in (cache, appdata, localappdata, temp):
        path.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "HF_HOME": str(ROOT / "models" / "hf_cache"),
            "HUGGINGFACE_HUB_CACHE": str(ROOT / "models" / "hf_cache" / "hub"),
            "XDG_CACHE_HOME": str(cache),
            "TORCH_HOME": str(cache / "torch"),
            "TRITON_CACHE_DIR": str(cache / "triton"),
            "FLASHINFER_WORKSPACE_DIR": str(cache / "flashinfer"),
            "TORCH_EXTENSIONS_DIR": str(cache / "torch_extensions"),
            "PIP_CACHE_DIR": str(cache / "pip"),
            "APPDATA": str(appdata),
            "LOCALAPPDATA": str(localappdata),
            "TEMP": str(temp),
            "TMP": str(temp),
        }
    )
    return env


def remote_size(repo_id: str, revision: str, filenames: list[str]) -> int:
    helper = '''
import json, sys
from huggingface_hub import HfApi
repo_id, revision, raw = sys.argv[1:4]
names = json.loads(raw)
info = HfApi().model_info(repo_id, revision=revision, files_metadata=True)
sizes = {item.rfilename: item.size for item in info.siblings if item.size is not None}
missing = [name for name in names if name not in sizes]
if missing:
    raise RuntimeError("missing metadata: " + ", ".join(missing))
print(sum(int(sizes[name]) for name in names))
'''
    proc = subprocess.run(
        [str(HF_PYTHON), "-c", helper, repo_id, revision, json.dumps(filenames)],
        capture_output=True,
        text=True,
        timeout=60,
        env=local_env(),
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip())
    return int(proc.stdout.strip())


def download_file(repo_id: str, revision: str, filename: str, local_dir: Path) -> None:
    helper = '''
import sys
from huggingface_hub import hf_hub_download
hf_hub_download(repo_id=sys.argv[1], filename=sys.argv[2], revision=sys.argv[3], local_dir=sys.argv[4])
'''
    proc = subprocess.run(
        [str(HF_PYTHON), "-c", helper, repo_id, filename, revision, str(local_dir)],
        env=local_env(),
        check=False,
    )
    if proc.returncode != 0:
        fail(f"download failed for {filename} (exit {proc.returncode}).")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install one trusted model entirely inside this tool folder.")
    parser.add_argument("model_id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not HF_PYTHON.is_file():
        fail("project-local FreeToken environment is missing; run Setup.bat first.")

    try:
        registry = ModelRegistry(ROOT)
        record = registry.require(args.model_id)
    except ModelRegistryError as exc:
        fail(str(exc))

    if not record.selectable:
        fail(f"{record.id} is compatibility-blocked on native Windows.")

    download = record.data.get("download")
    revision = record.data.get("revision")
    if not isinstance(download, dict):
        fail(f"{record.id} has no approved public download manifest.")
    if not isinstance(revision, str) or len(revision) != 40:
        fail(f"{record.id} does not have an immutable 40-character revision pin.")

    filenames = list(download["files"])
    try:
        remote_bytes = remote_size(str(record.data["hf_repo"]), revision, filenames)
    except Exception as exc:
        fail(f"could not read pinned Hugging Face metadata: {exc}")

    declared = int(download["expected_bytes"])
    tolerance = max(50_000_000, int(declared * 0.03))
    if abs(remote_bytes - declared) > tolerance:
        fail(f"pinned checkpoint size differs from registry estimate (registry={declared / GB:.2f} GB, remote={remote_bytes / GB:.2f} GB).")

    record.local_path.parent.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(record.local_path.parent).free
    reserve = int(registry.disk_reserve_gb * GB)
    if free < remote_bytes + reserve:
        fail(f"tool volume needs {(remote_bytes + reserve) / GB:.2f} GB free including reserve; only {free / GB:.2f} GB is available.")

    if args.dry_run:
        print(f"[Model Install] SAFE: {record.id}; payload {remote_bytes / GB:.2f} GB; tool-volume free {free / GB:.2f} GB; reserve {reserve / GB:.2f} GB.")
        return 0

    record.local_path.mkdir(parents=True, exist_ok=True)
    for filename in filenames:
        download_file(str(record.data["hf_repo"]), revision, filename, record.local_path)

    if not registry.is_installed(record):
        fail("download finished but required checkpoint files are incomplete.")
    print(f"[Model Install] INSTALLED: {record.id} at {record.local_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
