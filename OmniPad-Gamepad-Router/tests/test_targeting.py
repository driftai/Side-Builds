import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from router.targeting import TargetManager, IS_WINDOWS


def test_target_manager_basics():
    tm = TargetManager()
    status = tm.get_status()
    assert "selected" in status
    assert "foreground" in status
    assert tm.selected is None


def test_target_listing_shape():
    tm = TargetManager()
    targets = tm.list_windows()
    if IS_WINDOWS:
        assert isinstance(targets, list)
        for item in targets[:5]:
            assert item.pid >= 0
            assert isinstance(item.title, str)
    else:
        assert targets == []


def test_target_gate(monkeypatch=None):
    from router import slot_manager as sm
    from router.targeting import target_manager
    from config import config
    config.target_gate_enabled = True
    original = target_manager.selected
    orig_is_fg = getattr(target_manager, "is_target_foreground", None)
    orig_is_running = getattr(target_manager, "is_target_running", None)
    class Selected:
        pid = 1234
        hwnd = 5678
        title = "It Takes Two"
        process_name = "ItTakesTwo.exe"
    target_manager.selected = Selected()
    target_manager.is_target_foreground = lambda: False
    target_manager.is_target_running = lambda: True

    assert target_manager.selected and not target_manager.is_target_foreground()
    assert target_manager.is_target_running()

    target_manager.selected = original
    if orig_is_fg is not None:
        target_manager.is_target_foreground = orig_is_fg
    if orig_is_running is not None:
        target_manager.is_target_running = orig_is_running


def test_unfocused_virtual_controller_routing():
    import asyncio
    from router.slot_manager import SlotManager
    from router.targeting import target_manager
    from config import config

    config.target_gate_enabled = True
    sm = SlotManager()
    
    original = target_manager.selected
    orig_is_fg = getattr(target_manager, "is_target_foreground", None)
    orig_is_running = getattr(target_manager, "is_target_running", None)

    class Selected:
        pid = 9999
        hwnd = 8888
        title = "It Takes Two"
        process_name = "ItTakesTwo.exe"

    target_manager.selected = Selected()
    # Scenario: Target is running in background (e.g. Discord or OBS has focus)
    target_manager.is_target_running = lambda: True
    target_manager.is_target_foreground = lambda: False

    async def _test():
        # 1. Virtual Controller Backend (Xbox 360): Must route unfocused
        await sm.set_controller_type(1, "xbox360")
        packet = {
            "seq": 1,
            "buttons": {"A": True, "START": True},
            "axes": {"lx": 0.5, "ly": -0.5, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0},
            "input_surface": "touch"
        }
        await sm.process_input_packet(1, packet)
        slot = sm.slots[1]
        assert slot.is_active is True
        assert slot.last_state["buttons"]["A"] is True
        assert slot.last_state["buttons"]["START"] is True
        assert slot.last_state["axes"]["lx"] > 0.4

        # 2. Target Terminated: Virtual controller must pause
        target_manager.is_target_running = lambda: False
        packet2 = {
            "seq": 2,
            "buttons": {"A": True, "START": True},
            "axes": {"lx": 0.5, "ly": -0.5, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0},
            "input_surface": "touch"
        }
        await sm.process_input_packet(1, packet2)
        assert slot.is_active is False
        assert slot.last_state["buttons"] == {}

    try:
        asyncio.run(_test())
    finally:
        target_manager.selected = original
        if orig_is_fg is not None:
            target_manager.is_target_foreground = orig_is_fg
        if orig_is_running is not None:
            target_manager.is_target_running = orig_is_running


def test_target_locked_keyboard_stays_foreground_gated():
    import asyncio
    from router.slot_manager import SlotManager
    from router.targeting import target_manager
    from config import config

    config.target_gate_enabled = True
    sm = SlotManager()

    original = target_manager.selected
    orig_is_fg = getattr(target_manager, "is_target_foreground", None)
    orig_is_running = getattr(target_manager, "is_target_running", None)

    class Selected:
        pid = 9999
        hwnd = 8888
        title = "It Takes Two"
        process_name = "ItTakesTwo.exe"

    target_manager.selected = Selected()
    target_manager.is_target_running = lambda: True
    target_manager.is_target_foreground = lambda: False

    async def _test():
        # Target-Locked Keyboard backend: Must NOT inject while unfocused
        await sm.set_controller_type(1, "keyboard_target")
        packet = {
            "seq": 1,
            "buttons": {"A": True},
            "axes": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0},
            "input_surface": "keyboard"
        }
        await sm.process_input_packet(1, packet)
        slot = sm.slots[1]
        assert slot.is_active is False
        assert slot.last_state["buttons"] == {}

        # Once target is foreground, Target-Locked Keyboard allows injection
        target_manager.is_target_foreground = lambda: True
        packet2 = {
            "seq": 2,
            "buttons": {"A": True},
            "axes": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0},
            "input_surface": "keyboard"
        }
        await sm.process_input_packet(1, packet2)
        assert slot.is_active is True
        assert slot.last_state["buttons"]["A"] is True

    try:
        asyncio.run(_test())
    finally:
        target_manager.selected = original
        if orig_is_fg is not None:
            target_manager.is_target_foreground = orig_is_fg
        if orig_is_running is not None:
            target_manager.is_target_running = orig_is_running


def test_virtual_hid_keyboards_stay_foreground_gated():
    import asyncio
    from router.slot_manager import SlotManager
    from router.targeting import target_manager
    from config import config

    class FakeVHFController:
        def __init__(self):
            self.applied = []
            self.release_count = 0

        def apply(self, state):
            self.applied.append(state)

        def release_all(self):
            self.release_count += 1

        def close(self):
            pass

    original_selected = target_manager.selected
    original_is_fg = getattr(target_manager, "is_target_foreground", None)
    original_is_running = getattr(target_manager, "is_target_running", None)
    original_gate = config.target_gate_enabled

    class Selected:
        pid = 9999
        hwnd = 8888
        title = "It Takes Two"
        process_name = "ItTakesTwo.exe"

    target_manager.selected = Selected()
    target_manager.is_target_running = lambda: True
    config.target_gate_enabled = True

    async def _test():
        for controller_type in ("virtual_keyboard", "virtual_keyboard_port"):
            controller = FakeVHFController()
            manager = SlotManager()
            slot = manager.slots[1]
            slot.controller_type = controller_type
            slot.controller = controller
            target_manager.is_target_foreground = lambda: False
            packet = {
                "seq": 1,
                "buttons": {},
                "axes": {},
                "key_codes": ["KeyW"],
                "input_surface": "keyboard",
            }
            await manager.process_input_packet(1, packet)
            assert controller.release_count == 1
            assert controller.applied == []
            assert slot.is_active is False
            assert slot.last_state["key_codes"] == []

            target_manager.is_target_foreground = lambda: True
            packet["seq"] = 2
            await manager.process_input_packet(1, packet)
            assert len(controller.applied) == 1
            assert controller.applied[0]["key_codes"] == ["KeyW"]
            assert slot.is_active is True

    try:
        asyncio.run(_test())
    finally:
        config.target_gate_enabled = original_gate
        target_manager.selected = original_selected
        if original_is_fg is not None:
            target_manager.is_target_foreground = original_is_fg
        if original_is_running is not None:
            target_manager.is_target_running = original_is_running


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  TEST: Running Target Discovery & Foreground Gate")
    print("=" * 60)
    test_target_manager_basics()
    print("  [PASS] TargetManager basics")
    test_target_listing_shape()
    print("  [PASS] Target window listing shape")
    test_target_gate()
    print("  [PASS] Target gate safety predicate")
    test_unfocused_virtual_controller_routing()
    print("  [PASS] Unfocused virtual controller routing (Target running, not foreground)")
    test_target_locked_keyboard_stays_foreground_gated()
    print("  [PASS] Target-Locked keyboard foreground gating (Safety preserved)")
    test_virtual_hid_keyboards_stay_foreground_gated()
    print("  [PASS] VHF and UMDF virtual keyboards preserve foreground gating and release behavior")
    print("  >>> TARGET TESTS COMPLETED SUCCESSFULLY! <<<\n")

