#!/usr/bin/env python3
"""Low-noise architecture gate for OmniPad source-file sizing."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "MODULARIZATION-EXCEPTIONS.json"


def load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle)


def is_excluded(path: Path, excluded: set[str]) -> bool:
    return any(part in excluded for part in path.parts)


def main() -> int:
    config = load_config()
    max_lines = int(config.get("max_lines", 450))
    extensions = set(config.get("extensions", []))
    excluded = set(config.get("excluded_paths", []))
    exceptions = dict(config.get("legacy_exceptions", {}))

    violations: list[str] = []

    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in extensions:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if is_excluded(path.relative_to(ROOT), excluded):
            continue
        count = line_count(path)
        if count > max_lines and relative not in exceptions:
            violations.append(f"{relative}: {count} lines (max {max_lines})")

    if violations:
        print("ARCHITECTURE CHECK FAILED")
        for violation in violations:
            print(f" - {violation}")
        return 1

    print("Architecture check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
