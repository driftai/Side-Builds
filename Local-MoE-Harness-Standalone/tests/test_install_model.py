from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "install_model_script", ROOT / "scripts" / "install-model.py"
)
assert SPEC is not None and SPEC.loader is not None
install_model = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = install_model
SPEC.loader.exec_module(install_model)


class InstallModelStorageTests(unittest.TestCase):
    def test_storage_size_prints_decimal_and_binary_units(self):
        self.assertEqual(
            install_model.format_storage_size(18_825_669_933),
            "18.83 GB (17.53 GiB)",
        )

    def test_existing_selected_bytes_counts_only_present_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "one.bin").write_bytes(b"1234")
            (root / "two.bin").write_bytes(b"12")
            self.assertEqual(
                install_model.existing_selected_bytes(
                    root, ["one.bin", "missing.bin", "two.bin"]
                ),
                6,
            )

    def test_storage_accounting_reports_all_three_layers(self):
        gib = install_model.GIB
        before = install_model.StorageSnapshot(150 * gib, 90 * gib, 320 * gib)
        after = install_model.StorageSnapshot(132 * gib, 72 * gib, 338 * gib)
        message, amplified = install_model.storage_accounting(
            before, after, 18 * gib
        )
        self.assertIn("WSL logical used +18.00 GiB", message)
        self.assertIn("VHDX file +18.00 GiB", message)
        self.assertIn("Windows free -18.00 GiB", message)
        self.assertFalse(amplified)

    def test_storage_accounting_warns_on_material_amplification(self):
        gib = install_model.GIB
        before = install_model.StorageSnapshot(150 * gib, 90 * gib, None)
        after = install_model.StorageSnapshot(128 * gib, 72 * gib, None)
        _, amplified = install_model.storage_accounting(before, after, 18 * gib)
        self.assertTrue(amplified)


if __name__ == "__main__":
    unittest.main()
