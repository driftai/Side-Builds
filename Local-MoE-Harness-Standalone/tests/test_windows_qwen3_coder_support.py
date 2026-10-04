from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "apply-windows-freetoken-patch.py"
PATCH = ROOT / "runtime-patches" / "freetoken" / "15-qwen3-coder-fp8.patch"
PATCH_SHA256 = "5d7d34e1fdf2c041e3eab9fbf8a9c086d51005374ad83b87f8c5387d35e2ece1"
WINDOWS_FREETOKEN_VERSION = "0.1.2+g141c31a8d"
WINDOWS_FREETOKEN_WHEEL_SHA256 = "cb8ef0c1fa27e3bbd5fd6a812684cd025a639b79a4e3bc0169b2ce369b192f69"


def load_applier():
    spec = importlib.util.spec_from_file_location("windows_freetoken_patch_applier", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load Windows FreeToken patch applier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class WindowsQwen3CoderSupportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.applier = load_applier()

    def test_windows_manifest_pins_exact_approved_patch(self):
        config = json.loads(
            (ROOT / "config" / "windows-runtime.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["freetoken"]["version"], WINDOWS_FREETOKEN_VERSION)
        self.assertEqual(
            config["freetoken"]["wheel_sha256"], WINDOWS_FREETOKEN_WHEEL_SHA256
        )
        patches = config["freetoken"]["compatibility_patches"]
        self.assertEqual(len(patches), 1)
        patch = patches[0]
        self.assertEqual(patch["id"], "qwen3-coder-fp8")
        self.assertEqual(
            patch["file"],
            "runtime-patches/freetoken/15-qwen3-coder-fp8.patch",
        )
        self.assertEqual(patch["sha256"], PATCH_SHA256)
        self.assertEqual(patch["scope"], "python/freetoken/models/qwen3_moe/")
        self.assertEqual(hashlib.sha256(PATCH.read_bytes()).hexdigest(), PATCH_SHA256)

    def test_windows_qwen3_coder_policy_is_selectable_validated_and_patch_gated(self):
        policy = json.loads(
            (ROOT / "config" / "platform-policy.json").read_text(encoding="utf-8")
        )
        coder = policy["windows"]["models"]["qwen3-coder-30b-fp8"]
        self.assertTrue(coder["selectable"])
        self.assertEqual(coder["validation"], "windows_validated")
        self.assertEqual(coder["support"], "validated-project-path")
        self.assertEqual(coder["runtime_patch"]["id"], "qwen3-coder-fp8")
        self.assertEqual(coder["runtime_patch"]["sha256"], PATCH_SHA256)

    def test_setup_applies_manifest_patch_and_records_provenance(self):
        setup = (ROOT / "scripts" / "setup-windows.ps1").read_text(encoding="utf-8")
        self.assertIn("compatibility_patches", setup)
        self.assertIn("apply-windows-freetoken-patch.py", setup)
        self.assertIn("Assert-Hash $PatchPath", setup)
        self.assertIn("setup_offload_expert_banks", setup)
        self.assertIn("_fp8_block_quant", setup)
        self.assertIn("compatibility_patches = @($AppliedCompatibilityPatches)", setup)

    def test_runtime_registry_fails_closed_until_patch_is_proven(self):
        registry = (ROOT / "app" / "services" / "model_registry.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def _windows_runtime_patch_ready", registry)
        self.assertIn("windows-setup.json", registry)
        self.assertIn("freetoken_wheel_sha256", registry)
        self.assertIn("freetoken_version", registry)
        self.assertIn("windows_setup_required", registry)
        self.assertIn("setup-refresh-required", registry)
        self.assertIn("runtime_compatibility_ready", registry)
        self.assertIn("def _fp8_block_quant(", registry)
        self.assertIn("def setup_offload_expert_banks(", registry)

    def test_approved_patch_targets_only_validated_qwen3_moe_files(self):
        parsed = self.applier.parse_unified_diff(PATCH.read_text(encoding="utf-8"))
        self.assertEqual(
            {item.new_path for item in parsed},
            {
                "python/freetoken/models/qwen3_moe/config.py",
                "python/freetoken/models/qwen3_moe/attention.py",
                "python/freetoken/models/qwen3_moe/moe.py",
                "python/freetoken/models/qwen3_moe/weight.py",
                "python/freetoken/models/qwen3_moe/__init__.py",
            },
        )

    def test_stdlib_applier_applies_matching_patch_after_full_validation(self):
        patch_text = (
            "--- a/python/freetoken/models/qwen3_moe/sample.py\n"
            "+++ b/python/freetoken/models/qwen3_moe/sample.py\n"
            "@@ -1,2 +1,2 @@\n"
            " keep\n"
            "-old\n"
            "+new\n"
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            site = root / "site-packages"
            target = site / "freetoken" / "models" / "qwen3_moe" / "sample.py"
            target.parent.mkdir(parents=True)
            target.write_text("keep\nold\n", encoding="utf-8")
            patch_path = root / "sample.patch"
            patch_path.write_text(patch_text, encoding="utf-8")
            digest = hashlib.sha256(patch_path.read_bytes()).hexdigest()

            changed = self.applier.apply_patch(site, patch_path, digest)

            self.assertEqual(changed, [target.resolve()])
            self.assertEqual(target.read_text(encoding="utf-8"), "keep\nnew\n")

    def test_stdlib_applier_fails_closed_on_hash_or_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            site = root / "site-packages"
            target = site / "freetoken" / "models" / "other" / "sample.py"
            target.parent.mkdir(parents=True)
            target.write_text("old\n", encoding="utf-8")
            patch_path = root / "bad.patch"
            patch_path.write_text(
                "--- a/python/freetoken/models/other/sample.py\n"
                "+++ b/python/freetoken/models/other/sample.py\n"
                "@@ -1 +1 @@\n"
                "-old\n"
                "+new\n",
                encoding="utf-8",
            )
            digest = hashlib.sha256(patch_path.read_bytes()).hexdigest()

            with self.assertRaises(self.applier.PatchError):
                self.applier.apply_patch(site, patch_path, "0" * 64)
            with self.assertRaises(self.applier.PatchError):
                self.applier.apply_patch(site, patch_path, digest)
            self.assertEqual(target.read_text(encoding="utf-8"), "old\n")


if __name__ == "__main__":
    unittest.main()
