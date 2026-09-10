#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "windows-gguf-prebuilt.json"


class PrebuiltGGUFError(RuntimeError):
    pass


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise PrebuiltGGUFError(f"Required GGUF prebuilt metadata is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PrebuiltGGUFError(f"Invalid GGUF prebuilt metadata: {path}: {exc}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _model_path(argv: list[str]) -> Path | None:
    for index, value in enumerate(argv):
        if value == "--model-path" and index + 1 < len(argv):
            return Path(argv[index + 1]).expanduser()
        if value.startswith("--model-path="):
            return Path(value.split("=", 1)[1]).expanduser()
    return None


def _is_gguf_model(path: Path | None) -> bool:
    if path is None:
        return False
    if path.suffix.lower() == ".gguf":
        return True
    try:
        return path.is_dir() and any(path.glob("*.gguf"))
    except OSError:
        return False


def _version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError as exc:
        raise PrebuiltGGUFError(f"Required package is not installed: {name}") from exc


def _require_exact_compatibility(config: dict, manifest: dict) -> None:
    if sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise PrebuiltGGUFError("The prebuilt GGUF extension is only qualified for Windows x86-64.")

    expected_python = str(config["python_major_minor"])
    actual_python = f"{sys.version_info.major}.{sys.version_info.minor}"
    if actual_python != expected_python:
        raise PrebuiltGGUFError(
            f"GGUF prebuilt Python mismatch: expected {expected_python}, got {actual_python}."
        )

    expected_ft = str(config["freetoken_version"])
    actual_ft = _version("freetoken")
    if actual_ft != expected_ft:
        raise PrebuiltGGUFError(
            f"GGUF prebuilt FreeToken mismatch: expected {expected_ft}, got {actual_ft}."
        )

    import torch

    expected_torch = str(config["torch_version"])
    actual_torch = str(torch.__version__)
    if actual_torch != expected_torch:
        raise PrebuiltGGUFError(
            f"GGUF prebuilt Torch mismatch: expected {expected_torch}, got {actual_torch}."
        )

    for key, expected in (
        ("python_major_minor", expected_python),
        ("freetoken_version", expected_ft),
        ("torch_version", expected_torch),
        ("module_name", str(config["module_name"])),
    ):
        actual = str(manifest.get(key, ""))
        if actual != expected:
            raise PrebuiltGGUFError(
                f"GGUF prebuilt manifest mismatch for {key}: expected {expected!r}, got {actual!r}."
            )


def _load_prebuilt_gguf_module() -> object:
    config = _load_json(CONFIG_PATH)
    if config.get("jit_fallback_allowed") is not False:
        raise PrebuiltGGUFError("GGUF public runtime policy requires JIT fallback to be disabled.")

    artifact = ROOT / str(config["artifact_path"])
    manifest_path = ROOT / str(config["artifact_manifest_path"])
    if not artifact.is_file():
        raise PrebuiltGGUFError(
            "Native-Windows GGUF support requires the release-qualified prebuilt kernel bundle. "
            f"Missing artifact: {artifact}. Do not install a global compiler as a fallback."
        )

    manifest = _load_json(manifest_path)
    expected_hash = str(manifest.get("sha256", "")).lower()
    if len(expected_hash) != 64:
        raise PrebuiltGGUFError(f"Invalid GGUF prebuilt SHA-256 in {manifest_path}.")
    try:
        int(expected_hash, 16)
    except ValueError as exc:
        raise PrebuiltGGUFError(f"Invalid GGUF prebuilt SHA-256 in {manifest_path}.") from exc

    actual_hash = _sha256(artifact)
    if actual_hash != expected_hash:
        raise PrebuiltGGUFError(
            f"GGUF prebuilt SHA-256 mismatch: expected {expected_hash}, got {actual_hash}."
        )

    _require_exact_compatibility(config, manifest)

    module_name = str(config["module_name"])
    spec = importlib.util.spec_from_file_location(module_name, artifact)
    if spec is None or spec.loader is None:
        raise PrebuiltGGUFError(f"Could not create an import spec for {artifact}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    required_ops = (
        "ggml_dequantize",
        "ggml_mul_mat_vec_a8",
        "ggml_mul_mat_a8",
        "ggml_moe_a8",
        "ggml_moe_a8_vec",
        "ggml_moe_get_block_size",
    )
    missing = [name for name in required_ops if not hasattr(module, name)]
    if missing:
        raise PrebuiltGGUFError(
            "GGUF prebuilt module is missing required ops: " + ", ".join(missing)
        )
    return module


def _ensure_sitecustomize() -> None:
    try:
        sitecustomize_path = Path(sys.prefix) / "Lib" / "site-packages" / "sitecustomize.py"
        if not sitecustomize_path.parent.is_dir():
            return
        desired = (
            "# Auto-generated by Local MoE Harness for Windows multiprocessing hook inheritance\n"
            "import os\n"
            "from pathlib import Path\n\n"
            "if os.environ.get('FREETOKEN_WINDOWS_PREBUILT_GGUF') == '1':\n"
            "    root_str = os.environ.get('LOCAL_MOE_PROJECT_ROOT')\n"
            "    if root_str and Path(root_str).is_dir():\n"
            "        root = Path(root_str)\n"
            "    else:\n"
            "        p = Path(__file__).resolve().parent\n"
            "        root = next((d for d in [p] + list(p.parents) if (d / 'scripts' / 'windows-freetoken-entry.py').is_file()), None)\n"
            "    if root:\n"
            "        entry = root / 'scripts' / 'windows-freetoken-entry.py'\n"
            "        if entry.is_file():\n"
            "            import importlib.util\n"
            "            spec = importlib.util.spec_from_file_location('_wfentry', entry)\n"
            "            if spec and spec.loader:\n"
            "                mod = importlib.util.module_from_spec(spec)\n"
            "                spec.loader.exec_module(mod)\n"
            "                mod._install_prebuilt_hook()\n"
        )
        current = (
            sitecustomize_path.read_text(encoding="utf-8")
            if sitecustomize_path.is_file()
            else ""
        )
        if current != desired:
            sitecustomize_path.write_text(desired, encoding="utf-8")
    except OSError:
        pass


def _install_prebuilt_hook() -> None:
    module = _load_prebuilt_gguf_module()
    import freetoken.kernel.gguf as gguf_kernel

    # FreeToken's GGUF helper normally invokes its Torch extension builder on first use.
    # Replace only its cached module factory; all higher-level GGUF layer/model code stays upstream.
    gguf_kernel._module = lambda: module


def main() -> int:
    model = _model_path(sys.argv[1:])
    if _is_gguf_model(model):
        os.environ["FREETOKEN_WINDOWS_PREBUILT_GGUF"] = "1"
        os.environ["LOCAL_MOE_PROJECT_ROOT"] = str(ROOT)
        _ensure_sitecustomize()
        try:
            _install_prebuilt_hook()
        except PrebuiltGGUFError as exc:
            print(f"[FreeToken/Windows] GGUF prebuilt bundle rejected: {exc}", file=sys.stderr)
            return 78

    from freetoken.cli import main as freetoken_main

    result = freetoken_main()
    return int(result) if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
