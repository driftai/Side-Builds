#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
target = ROOT / ("install-model-windows.py" if os.name == "nt" else "install-model-linux.py")


def _load_implementation():
    module_name = f"_local_moe_install_model_{'windows' if os.name == 'nt' else 'linux'}"
    spec = importlib.util.spec_from_file_location(module_name, target)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load model installer implementation: {target}")
    module = importlib.util.module_from_spec(spec)
    # Dataclasses and other import-time helpers expect their defining module to
    # be present in sys.modules while the implementation is executed.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_implementation = _load_implementation()
for _name in dir(_implementation):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_implementation, _name)


if __name__ == "__main__":
    raise SystemExit(_implementation.main())
