from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_LINES = 450
EXEMPT = {"intel_legacy.py"}
IGNORED_PARTS = {".venv", ".pytest_cache", "__pycache__"}


def test_runtime_modules_stay_within_house_line_cap() -> None:
    """Keep active project modules reviewable; frozen legacy compatibility is grandfathered."""
    oversized: dict[str, int] = {}
    for path in sorted(ROOT.rglob("*.py")):
        if any(part in path.parts for part in IGNORED_PARTS):
            continue
        if path.name in EXEMPT:
            continue
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > MAX_LINES:
            rel = str(path.relative_to(ROOT))
            oversized[rel] = line_count

    assert not oversized, (
        f"Runtime modules exceed the {MAX_LINES}-line house cap: {oversized}. "
        "Split by responsibility instead of raising the limit."
    )
