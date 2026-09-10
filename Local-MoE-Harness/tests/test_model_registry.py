import json
import io
import sys
import tempfile
import unittest
from pathlib import Path

from app.services.model_registry import ModelRegistry, ModelRegistryError


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ModelRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        document = json.loads(
            (PROJECT_ROOT / "config" / "models.json").read_text(encoding="utf-8")
        )
        (self.root / "config" / "models.json").write_text(
            json.dumps(document), encoding="utf-8"
        )
        self.document = document

    def tearDown(self):
        self.temp.cleanup()

    def _install(self, model_id):
        raw = next(item for item in self.document["models"] if item["id"] == model_id)
        target = self.root / raw["local_path"]
        for filename in raw["required_files"]:
            path = target / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"test")

    def test_qwen_legacy_profiles_are_preserved(self):
        registry = ModelRegistry(self.root)
        normal = registry.profile("qwen36-nvfp4", "normal")
        busy = registry.profile("qwen36-nvfp4", "busy")
        recovery = registry.profile("qwen36-nvfp4", "recovery")
        self.assertEqual((normal["kv_tokens"], normal["moe_slots"]), (12288, 569))
        self.assertEqual((busy["kv_tokens"], busy["moe_slots"]), (8192, 736))
        self.assertEqual(
            (recovery["kv_tokens"], recovery["prefill_tokens"], recovery["d2d"]),
            (4096, 1024, 0),
        )

    def test_selection_persists_only_for_installed_model(self):
        self._install("qwen36-nvfp4")
        registry = ModelRegistry(self.root)
        with self.assertRaisesRegex(ModelRegistryError, "not installed"):
            registry.persist_selection("gpt-oss-20b")
        self._install("gpt-oss-20b")
        registry.persist_selection("gpt-oss-20b")
        self.assertEqual(ModelRegistry(self.root).selected_model_id(), "gpt-oss-20b")

    def test_missing_persisted_model_falls_back_to_qwen(self):
        self._install("qwen36-nvfp4")
        state = self.root / "state" / "selected-model.json"
        state.parent.mkdir()
        state.write_text('{"model_id":"gpt-oss-20b"}', encoding="utf-8")
        self.assertEqual(ModelRegistry(self.root).selected_model_id(), "qwen36-nvfp4")

    def test_invalid_model_id_is_rejected(self):
        registry = ModelRegistry(self.root)
        with self.assertRaisesRegex(ModelRegistryError, "Unknown model id"):
            registry.require("../../arbitrary-model")

    def test_active_catalog_contains_only_supported_models(self):
        registry = ModelRegistry(self.root)
        models = {item["id"]: item for item in registry.public_models()}
        self.assertTrue(
            {
                "qwen36-nvfp4",
                "qwen3-coder-30b-fp8",
                "gpt-oss-20b",
                "gemma4-26b-q4_0-gguf",
            }
            <= models.keys()
        )
        self.assertTrue(
            {
                "gemma4-26b-nvfp4",
                "qwen3-30b-nvfp4",
                "muse-glimmer-30b-nvfp4",
                "qwen35-35b-a3b-bf16",
            }.isdisjoint(models)
        )
        self.assertEqual(models["gemma4-26b-q4_0-gguf"]["validation"], "validated")
        self.assertEqual(models["qwen3-coder-30b-fp8"]["validation"], "validated")

    def test_qwen_coder_is_pinned_validated_and_selectable(self):
        registry = ModelRegistry(self.root)
        record = registry.require("qwen3-coder-30b-fp8")
        public = next(
            item for item in registry.public_models() if item["id"] == record.id
        )
        self.assertEqual(
            record.data["revision"],
            "dcaee4d4dfc5ee71ad501f01f530e5652438fde0",
        )
        self.assertEqual(record.data["architecture"], "Qwen3MoeForCausalLM")
        self.assertEqual(record.data["default_reasoning_effort"], "none")
        self.assertTrue(record.selectable)
        self.assertTrue(public["download_supported"])
        self.assertEqual(public["validation"], "validated")
        self.assertEqual(public["availability"], "available")
        normal = registry.profile(record.id, "normal")
        busy = registry.profile(record.id, "busy")
        recovery = registry.profile(record.id, "recovery")
        self.assertEqual((normal["kv_tokens"], normal["prefill_tokens"], normal["memory_ratio"]), (4096, 1024, 0.88))
        self.assertEqual((busy["kv_tokens"], busy["prefill_tokens"], busy["memory_ratio"]), (2048, 512, 0.80))
        self.assertEqual((recovery["kv_tokens"], recovery["prefill_tokens"], recovery["memory_ratio"]), (2048, 512, 0.80))

        self._install(record.id)
        installed = ModelRegistry(self.root)
        installed.persist_selection(record.id)
        self.assertEqual(ModelRegistry(self.root).selected_model_id(), record.id)

    def test_qwen_coder_manifest_excludes_remote_python_helpers(self):
        registry = ModelRegistry(self.root)
        record = registry.require("qwen3-coder-30b-fp8")
        files = set(record.data["download"]["files"])
        self.assertNotIn("qwen3coder_tool_parser.py", files)
        self.assertTrue(
            {
                "config.json",
                "model-00001-of-00004.safetensors",
                "model-00002-of-00004.safetensors",
                "model-00003-of-00004.safetensors",
                "model-00004-of-00004.safetensors",
                "model.safetensors.index.json",
                "tokenizer.json",
            }
            <= files
        )

    def test_registry_rejects_model_path_outside_models(self):
        self.document["models"][0]["local_path"] = "../runtime/freetoken"
        (self.root / "config" / "models.json").write_text(
            json.dumps(self.document), encoding="utf-8"
        )
        with self.assertRaisesRegex(ModelRegistryError, "inside the project"):
            ModelRegistry(self.root)

    def test_directory_model_runtime_path_is_unchanged(self):
        registry = ModelRegistry(self.root)
        record = registry.require("qwen36-nvfp4")
        self.assertEqual(record.runtime_path, record.local_path)

    def test_safe_single_file_runtime_path_is_resolved_under_model(self):
        registry = ModelRegistry(self.root)
        record = registry.require("gemma4-26b-q4_0-gguf")
        self.assertEqual(
            record.runtime_path,
            record.local_path / "gemma-4-26B_q4_0-it.gguf",
        )

    def test_registry_rejects_absolute_serve_file(self):
        model = next(
            item
            for item in self.document["models"]
            if item["id"] == "gemma4-26b-q4_0-gguf"
        )
        model["serve_file"] = "/tmp/foreign.gguf"
        (self.root / "config" / "models.json").write_text(
            json.dumps(self.document), encoding="utf-8"
        )
        with self.assertRaisesRegex(ModelRegistryError, "safe relative path"):
            ModelRegistry(self.root)

    def test_registry_rejects_serve_file_escape(self):
        model = next(
            item
            for item in self.document["models"]
            if item["id"] == "gemma4-26b-q4_0-gguf"
        )
        model["serve_file"] = "../foreign.gguf"
        (self.root / "config" / "models.json").write_text(
            json.dumps(self.document), encoding="utf-8"
        )
        with self.assertRaisesRegex(ModelRegistryError, "safe relative path"):
            ModelRegistry(self.root)

    def test_missing_serve_file_is_not_installed(self):
        registry = ModelRegistry(self.root)
        self.assertFalse(registry.is_installed("gemma4-26b-q4_0-gguf"))

    def test_external_required_file_symlink_is_not_installed(self):
        model = next(
            item
            for item in self.document["models"]
            if item["id"] == "gemma4-26b-q4_0-gguf"
        )
        target = self.root / model["local_path"]
        target.mkdir(parents=True)
        foreign = self.root / "foreign.gguf"
        foreign.write_bytes(b"foreign")
        (target / model["serve_file"]).symlink_to(foreign)
        with self.assertRaisesRegex(ModelRegistryError, "inside the model directory"):
            ModelRegistry(self.root)


if __name__ == "__main__":
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    if result.wasSuccessful():
        print(f"[Model Registry Tests] PASS ({result.testsRun}/{result.testsRun})")
        raise SystemExit(0)
    print("\n".join(stream.getvalue().splitlines()[-40:]), file=sys.stderr)
    raise SystemExit(1)
