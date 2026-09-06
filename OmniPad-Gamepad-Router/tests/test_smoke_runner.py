"""Regression tests for the low-noise smoke-suite aggregator."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.run_smoke_tests import ACTIONABLE_MARKERS, RESULT_PATH, SUITES, actionable_lines, relevant_lines


def test_stage_manifest() -> None:
    stage_ids = [stage_id for stage_id, _ in SUITES]
    assert len(stage_ids) == len(set(stage_ids)), "smoke stage IDs must be unique"
    assert stage_ids[0] == "architecture", "architecture must remain the first integration gate"
    assert "smoke_runner" in stage_ids, "the aggregator must test its own output contract"
    for _, script in SUITES:
        assert (ROOT / script).is_file(), f"smoke stage is missing: {script}"


def test_output_contract() -> None:
    batch = (ROOT / "tools" / "run_smoke_tests.bat").read_text(encoding="utf-8").lower()
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "run_smoke_tests.py" in batch
    assert "pause" not in batch, "the reusable runner must not block automation"
    assert "test-results/" in ignore
    assert RESULT_PATH == ROOT / "test-results" / "smoke.json"

    lines = relevant_lines({"stdout": "\n".join(str(i) for i in range(60)), "stderr": ""})
    assert len(lines) == 40
    assert lines[0] == "20" and lines[-1] == "59"
    assert "warning" in ACTIONABLE_MARKERS
    assert actionable_lines({"stdout": "routine\nWARNING: inspect this", "stderr": ""}) == [
        "WARNING: inspect this"
    ]


def main() -> None:
    test_stage_manifest()
    test_output_contract()
    print("PASS smoke runner regression: manifest, bounded output, and diagnostics artifact.")


if __name__ == "__main__":
    main()
