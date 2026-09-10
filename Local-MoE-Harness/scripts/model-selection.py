#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.model_registry import ModelRegistry, ModelRegistryError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage trusted local model selection state.")
    parser.add_argument(
        "action",
        choices=("selected", "default", "select-default", "startup-timeout"),
    )
    parser.add_argument(
        "--profile",
        choices=("normal", "busy", "recovery"),
        help="Runtime profile used by startup-timeout.",
    )
    args = parser.parse_args()
    registry = ModelRegistry(ROOT)

    if args.action == "selected":
        print(registry.selected_model_id())
    elif args.action == "default":
        print(registry.default_model_id)
    elif args.action == "select-default":
        registry.persist_selection(registry.default_model_id)
        print(registry.default_model_id)
    else:
        if args.profile is None:
            parser.error("startup-timeout requires --profile normal, busy, or recovery")
        model_id = registry.selected_model_id()
        try:
            timeout = int(registry.profile(model_id, args.profile)["startup_timeout"])
        except (KeyError, TypeError, ValueError, ModelRegistryError) as exc:
            parser.error(f"could not resolve startup timeout for {model_id}/{args.profile}: {exc}")
        if timeout <= 0:
            parser.error(
                f"startup timeout for {model_id}/{args.profile} must be positive"
            )
        print(timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
