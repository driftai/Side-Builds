import json
import tempfile
import unittest
from pathlib import Path

from app.services.model_registry import ModelRegistry, ModelRegistryError


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ModelLocationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "harness"
        self.root.mkdir()
        (self.root / "config").mkdir()
        document = json.loads(
            (PROJECT_ROOT / "config" / "models.json").read_text(encoding="utf-8")
        )
        (self.root / "config" / "models.json").write_text(
            json.dumps(document), encoding="utf-8"
        )
        (self.root / "config" / "platform-policy.json").write_text(
            '{"schema_version":1}', encoding="utf-8"
        )
        self.document = document

    def tearDown(self):
        self.temp.cleanup()

    def _required_files(self, model_id: str, target: Path) -> None:
        raw = next(item for item in self.document["models"] if item["id"] == model_id)
        for filename in raw["required_files"]:
            path = target / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"model-test")

    def test_external_location_persists_and_is_detected(self):
        external = Path(self.temp.name) / "external-drive" / "qwen"
        self._required_files("qwen36-nvfp4", external)

        registry = ModelRegistry(self.root)
        record = registry.set_model_location("qwen36-nvfp4", str(external.resolve()))
        self.assertEqual(record.local_path, external.resolve())
        self.assertTrue(registry.is_installed(record))

        reloaded = ModelRegistry(self.root)
        record = reloaded.require("qwen36-nvfp4")
        self.assertEqual(record.local_path, external.resolve())
        self.assertTrue(reloaded.is_installed(record))
        public = next(
            item for item in reloaded.public_models(include_paths=True)
            if item["id"] == "qwen36-nvfp4"
        )
        self.assertEqual(public["location_source"], "external")
        self.assertEqual(public["model_path"], str(external.resolve()))

    def test_disconnected_external_location_stays_linked_but_not_installed(self):
        external = Path(self.temp.name) / "removable-drive" / "rare-model"
        registry = ModelRegistry(self.root)
        registry.set_model_location("gpt-oss-20b", str(external.resolve()))

        reloaded = ModelRegistry(self.root)
        record = reloaded.require("gpt-oss-20b")
        self.assertFalse(reloaded.is_installed(record))
        public = next(
            item for item in reloaded.public_models(include_paths=True)
            if item["id"] == "gpt-oss-20b"
        )
        self.assertTrue(public["location_configured"])
        self.assertFalse(public["location_available"])

    def test_reset_restores_default_project_location(self):
        registry = ModelRegistry(self.root)
        default_path = registry.require("qwen36-nvfp4").local_path
        external = Path(self.temp.name) / "external" / "qwen"
        registry.set_model_location("qwen36-nvfp4", str(external.resolve()))
        restored = registry.reset_model_location("qwen36-nvfp4")
        self.assertEqual(restored.local_path, default_path)
        self.assertNotIn(
            "qwen36-nvfp4",
            json.loads(
                (self.root / "state" / "model-locations.json").read_text(encoding="utf-8")
            )["models"],
        )

    def test_relative_location_is_rejected(self):
        registry = ModelRegistry(self.root)
        with self.assertRaisesRegex(ModelRegistryError, "absolute path"):
            registry.set_model_location("qwen36-nvfp4", "../somewhere")

    def test_paths_are_redacted_from_default_public_view(self):
        registry = ModelRegistry(self.root)
        public = next(
            item for item in registry.public_models()
            if item["id"] == "qwen36-nvfp4"
        )
        self.assertFalse(public["path_visible"])
        self.assertNotIn("model_path", public)
        self.assertNotIn("runtime_path", public)

    def test_single_file_model_accepts_direct_file_path(self):
        raw = next(
            item
            for item in self.document["models"]
            if item["id"] == "gemma4-26b-q4_0-gguf"
        )
        external = Path(self.temp.name) / "portable-gguf"
        external.mkdir()
        gguf = external / raw["serve_file"]
        gguf.write_bytes(b"gguf-test")

        registry = ModelRegistry(self.root)
        record = registry.set_model_location(
            "gemma4-26b-q4_0-gguf", str(gguf.resolve())
        )
        self.assertEqual(record.local_path, external.resolve())
        self.assertEqual(record.runtime_path, gguf.resolve())
        self.assertTrue(registry.is_installed(record))


if __name__ == "__main__":
    unittest.main()
