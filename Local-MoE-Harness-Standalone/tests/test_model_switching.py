import io
import sys
import unittest

from app.services.model_switching import ModelSwitchCoordinator, ModelSwitchError


class Record:
    def __init__(self, model_id):
        self.id = model_id


class FakeRegistry:
    default_model_id = "qwen"

    def __init__(self):
        self.selected = "qwen"
        self.persisted = []

    def require_selectable_installed(self, model_id):
        if model_id not in {"qwen", "alternate"}:
            raise ValueError("unknown")
        return Record(model_id)

    def selected_model_id(self):
        return self.selected

    def persist_selection(self, model_id):
        self.selected = model_id
        self.persisted.append(model_id)

    def profile(self, model_id, name):
        return {"moe_slots": 10, "request_timeout": 300 if name == "normal" else 1200}


class FakeLifecycle:
    def __init__(self, fail_target=False):
        self.active_model_id = "qwen"
        self.active_profile_name = "normal"
        self.startup_stage = "ready"
        self.fail_target = fail_target
        self.starts = []
        self.stops = 0

    async def stop_managed(self):
        self.stops += 1
        self.startup_stage = "stopped"

    async def start_model(self, model_id, *, wait_until_ready):
        self.starts.append(model_id)
        self.active_model_id = model_id
        self.startup_stage = "ready"
        if model_id == "alternate" and self.fail_target:
            return {"ready": False, "error": "deterministic startup failure"}
        return {"ready": True}


class FakeAdapter:
    async def status(self):
        return {"ready": True}


class FakeGpu:
    def __init__(self, reject_switch=False):
        self.reject_switch = reject_switch
        self.reserved = False
        self.running = True
        self.configured = []

    async def reserve_model_switch(self):
        if self.reject_switch:
            raise RuntimeError("Cannot switch models during an active request.")
        self.reserved = True

    async def release_model_switch(self):
        self.reserved = False

    async def stop(self):
        self.running = False

    async def start(self):
        self.running = True

    def configure_runtime_profile(self, normal, busy, *, active_profile_name):
        self.configured.append(active_profile_name)


class FakeMemory:
    def __init__(self):
        self.resets = 0

    def reset_all(self):
        self.resets += 1
        return 2


class ModelSwitchingTests(unittest.IsolatedAsyncioTestCase):
    def make_coordinator(self, *, fail_target=False, reject_switch=False):
        registry = FakeRegistry()
        lifecycle = FakeLifecycle(fail_target=fail_target)
        gpu = FakeGpu(reject_switch=reject_switch)
        memory = FakeMemory()
        coordinator = ModelSwitchCoordinator(
            registry, lifecycle, FakeAdapter(), gpu, memory
        )
        return coordinator, registry, lifecycle, gpu, memory

    async def test_successful_switch_persists_and_resets_conversations(self):
        coordinator, registry, lifecycle, gpu, memory = self.make_coordinator()
        result = await coordinator.switch("alternate")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(registry.persisted, ["alternate"])
        self.assertEqual(memory.resets, 1)
        self.assertEqual(lifecycle.starts, ["alternate"])
        self.assertTrue(gpu.running)
        self.assertFalse(gpu.reserved)

    async def test_failed_alternate_switch_restores_previous_model(self):
        coordinator, registry, lifecycle, gpu, memory = self.make_coordinator(
            fail_target=True
        )
        with self.assertRaises(ModelSwitchError) as caught:
            await coordinator.switch("alternate")
        self.assertEqual(caught.exception.restored_model_id, "qwen")
        self.assertEqual(lifecycle.starts, ["alternate", "qwen"])
        self.assertEqual(registry.persisted, ["qwen"])
        self.assertEqual(memory.resets, 0)
        self.assertTrue(gpu.running)
        self.assertFalse(gpu.reserved)

    async def test_switch_is_rejected_during_active_request(self):
        coordinator, registry, lifecycle, gpu, memory = self.make_coordinator(
            reject_switch=True
        )
        with self.assertRaisesRegex(ModelSwitchError, "active request"):
            await coordinator.switch("alternate")
        self.assertEqual(lifecycle.stops, 0)
        self.assertEqual(registry.persisted, [])
        self.assertEqual(memory.resets, 0)


if __name__ == "__main__":
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    if result.wasSuccessful():
        print(f"[Model Switching Tests] PASS ({result.testsRun}/{result.testsRun})")
        raise SystemExit(0)
    print("\n".join(stream.getvalue().splitlines()[-40:]), file=sys.stderr)
    raise SystemExit(1)
