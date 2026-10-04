from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "warmup_harness", ROOT / "scripts" / "warmup-harness.py"
)
assert SPEC and SPEC.loader
warmup_harness = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = warmup_harness
SPEC.loader.exec_module(warmup_harness)


class WarmupHarnessTests(unittest.TestCase):
    def test_managed_runtime_death_fails_without_waiting_for_timeout(self) -> None:
        status = {
            "runtime": {"ready": False, "phase": "unknown"},
            "runtime_lifecycle": {
                "managed_running": False,
                "startup_stage": "loading_weights",
                "last_error": None,
            },
        }
        with patch.object(warmup_harness, "get_json", return_value=status):
            with self.assertRaisesRegex(RuntimeError, "exited before readiness"):
                warmup_harness.wait_until_ready(255)

    def test_unmanaged_idle_status_is_not_misclassified_as_process_death(self) -> None:
        status = {
            "runtime_lifecycle": {
                "managed_running": False,
                "startup_stage": "idle",
            }
        }
        self.assertIsNone(warmup_harness.managed_runtime_failure(status))


if __name__ == "__main__":
    unittest.main()
