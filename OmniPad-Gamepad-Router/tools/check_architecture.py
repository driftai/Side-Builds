#!/usr/bin/env python3
"""Low-noise architecture gate for OmniPad source-file sizing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "MODULARIZATION-EXCEPTIONS.json"
RESULT_PATH = ROOT / "test-results" / "architecture.json"
REQUIRED_EXCEPTION_FIELDS = ("owner", "reason", "removal_target")


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle)


def is_excluded(path: Path, excluded: set[str]) -> bool:
    return any(part.casefold() in excluded for part in path.parts)


def inspect_tree(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    max_lines = int(config.get("max_lines", 450))
    extensions = {str(value).lower() for value in config.get("extensions", [])}
    excluded = {str(value).casefold() for value in config.get("excluded_paths", [])}
    exceptions = dict(config.get("legacy_exceptions", {}))
    files: list[dict[str, Any]] = []
    violations: list[str] = []
    used_exceptions: set[str] = set()

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        relative_path = path.relative_to(root)
        if is_excluded(relative_path, excluded):
            continue

        relative = relative_path.as_posix()
        count = line_count(path)
        files.append({"path": relative, "lines": count})
        if count <= max_lines:
            continue

        exception = exceptions.get(relative)
        if exception is None:
            violations.append(f"{relative}: {count} lines (max {max_lines})")
            continue

        used_exceptions.add(relative)
        if not isinstance(exception, dict):
            violations.append(f"{relative}: exception metadata must be an object")
            continue
        missing = [field for field in REQUIRED_EXCEPTION_FIELDS if not exception.get(field)]
        if missing:
            violations.append(f"{relative}: exception missing {', '.join(missing)}")

    for relative in sorted(exceptions):
        if relative not in used_exceptions:
            violations.append(f"{relative}: stale exception; file is absent or within the limit")

    files.sort(key=lambda item: (-item["lines"], item["path"]))
    return {
        "status": "pass" if not violations else "fail",
        "max_lines": max_lines,
        "covered_files": len(files),
        "largest": files[0] if files else None,
        "exceptions": len(used_exceptions),
        "violations": violations,
        "files": files,
    }


def write_result(result: dict[str, Any], path: Path = RESULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    try:
        result = inspect_tree(ROOT, load_config())
    except Exception as exc:
        result = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        write_result(result)
        print(f"FAIL architecture: {result['error']} (details: {RESULT_PATH})")
        return 1

    write_result(result)
    if result["violations"]:
        print(
            f"FAIL architecture: {len(result['violations'])} violation(s); "
            f"details: {RESULT_PATH}"
        )
        for violation in result["violations"][:40]:
            print(f" - {violation}")
        return 1

    largest = result["largest"] or {"path": "none", "lines": 0}
    print(
        f"PASS architecture: {result['covered_files']} files, max {result['max_lines']}, "
        f"largest {largest['path']} ({largest['lines']}), "
        f"{result['exceptions']} exceptions."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
