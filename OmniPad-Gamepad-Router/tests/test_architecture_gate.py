"""Regression tests for the repository-wide 450-line architecture gate."""

from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.check_architecture import inspect_tree, load_config


def base_config() -> dict:
    return {
        "max_lines": 450,
        "extensions": [".py", ".css", ".c", ".ps1"],
        "excluded_paths": ["vendor", "test-results"],
        "legacy_exceptions": {},
    }


def write_lines(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("line\n" * count, encoding="utf-8")


def test_current_scope_contract() -> None:
    config = load_config()
    extensions = set(config["extensions"])
    excluded = set(config["excluded_paths"])

    for extension in (".py", ".js", ".css", ".html", ".c", ".h", ".ps1", ".bat"):
        assert extension in extensions, f"first-party {extension} source is not covered"
    assert "drivers" not in excluded, "driver source must not bypass the line ceiling"
    assert "tests" not in excluded, "test harness source must not bypass the line ceiling"


def test_overages_and_exclusions() -> None:
    with tempfile.TemporaryDirectory(prefix="omnipad-architecture-") as temp:
        root = Path(temp)
        write_lines(root / "normal.py", 450)
        write_lines(root / "styles.css", 451)
        write_lines(root / "drivers" / "device.c", 452)
        write_lines(root / "vendor" / "third_party.c", 900)

        result = inspect_tree(root, base_config())
        assert result["status"] == "fail"
        assert result["covered_files"] == 3
        assert len(result["violations"]) == 2
        assert any("styles.css: 451" in item for item in result["violations"])
        assert any("drivers/device.c: 452" in item for item in result["violations"])
        assert not any("third_party" in item for item in result["violations"])


def test_exception_metadata_and_stale_debt() -> None:
    with tempfile.TemporaryDirectory(prefix="omnipad-exceptions-") as temp:
        root = Path(temp)
        write_lines(root / "legacy.ps1", 451)

        config = base_config()
        config["legacy_exceptions"] = {"legacy.ps1": {"owner": "runtime"}}
        result = inspect_tree(root, config)
        assert any("exception missing reason, removal_target" in item for item in result["violations"])

        config["legacy_exceptions"] = {
            "legacy.ps1": {
                "owner": "runtime",
                "reason": "temporary migration debt",
                "removal_target": "next modularization pass",
            }
        }
        assert inspect_tree(root, config)["status"] == "pass"

        write_lines(root / "legacy.ps1", 450)
        result = inspect_tree(root, config)
        assert any("stale exception" in item for item in result["violations"])


def main() -> None:
    test_current_scope_contract()
    test_overages_and_exclusions()
    test_exception_metadata_and_stale_debt()
    print("PASS architecture gate regression: scope, overages, exclusions, and exception debt.")


if __name__ == "__main__":
    main()
