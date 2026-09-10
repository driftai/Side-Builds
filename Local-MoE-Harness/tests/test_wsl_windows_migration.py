from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WslToWindowsMigrationTests(unittest.TestCase):
    def test_windows_setup_rehydrates_copied_wsl_runtime_state(self):
        text = (ROOT / "scripts" / "setup-windows.ps1").read_text(encoding="utf-8")
        self.assertIn("Linux/WSL runtime artifacts detected", text)
        self.assertIn('.venv\\bin\\python', text)
        self.assertIn('.venvs\\freetoken\\bin\\python', text)
        self.assertIn('.venv\\bin\\activate', text)
        self.assertIn('.venvs\\freetoken\\bin\\activate', text)
        self.assertIn('$DisposableRuntimePaths = @(', text)
        self.assertIn('tools\\python', text)
        self.assertIn('tools\\uv', text)
        self.assertIn('.cache\\torch_extensions', text)
        self.assertIn('state\\harness.pid', text)
        self.assertIn('state\\freetoken.pid', text)
        self.assertIn('--managed-python --clear', text)

    def test_wsl_rehydration_preserves_durable_project_data(self):
        text = (ROOT / "scripts" / "setup-windows.ps1").read_text(encoding="utf-8")
        start = text.index('$DisposableRuntimePaths = @(')
        end = text.index('    foreach ($Relative in $DisposableRuntimePaths)', start)
        cleanup_block = text[start:end]
        for durable in ('"models"', '"config"', '"vendor"', '"tools\\downloads"'):
            self.assertNotIn(durable, cleanup_block)

    def test_qualified_windows_gemma_policy_is_recorded(self):
        policy = json.loads((ROOT / "config" / "platform-policy.json").read_text(encoding="utf-8"))
        gemma = policy["windows"]["models"]["gemma4-26b-q4_0-gguf"]
        self.assertTrue(gemma["selectable"])
        self.assertEqual(gemma["validation"], "windows_validated")
        self.assertEqual(gemma["support"], "validated-project-path")

    def test_qualified_windows_qwen36_policy_is_recorded(self):
        policy = json.loads((ROOT / "config" / "platform-policy.json").read_text(encoding="utf-8"))
        qwen = policy["windows"]["models"]["qwen36-nvfp4"]
        self.assertTrue(qwen["selectable"])
        self.assertEqual(qwen["validation"], "windows_validated")
        self.assertEqual(qwen["support"], "validated-project-path")


if __name__ == "__main__":
    unittest.main()
