import asyncio
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.slot_manager import SlotManager
from router.controller import (
    Xbox360Backend,
    DualShock4Backend,
    TargetLockedKeyboardBackend,
    KeyboardInjectionBackend,
    VirtualKeyboardHIDBackend,
)


async def run_backend_transition_test():
    print("\n" + "=" * 60)
    print("  TEST: Backend Transitions & Transactional Resilience")
    print("=" * 60)

    sm = SlotManager()

    slot = sm.slots.get(1)
    assert slot is not None
    # Initialize slot 1 controller to default
    await sm.set_controller_type(1, "xbox360")
    print(f"  [PASS] Initialized Slot 1 with default: {slot.controller_type}")
    assert isinstance(slot.controller, Xbox360Backend)

    # 1. Switch to DS4
    ok = await sm.set_controller_type(1, "ds4")
    assert ok is True
    assert isinstance(slot.controller, DualShock4Backend)
    print("  [PASS] Switched Slot 1 to DualShock 4")

    # 2. Switch to Keyboard 2 (Target-Locked SendInput)
    ok = await sm.set_controller_type(1, "keyboard_target")
    assert ok is True
    assert isinstance(slot.controller, TargetLockedKeyboardBackend)
    print("  [PASS] Switched Slot 1 to Keyboard 2 (Target-Locked SendInput)")

    # 3. Switch to Legacy Keyboard & Verify Raw Key Preservation
    ok = await sm.set_controller_type(1, "keyboard")
    assert ok is True
    assert isinstance(slot.controller, KeyboardInjectionBackend)
    print("  [PASS] Switched Slot 1 to Legacy Keyboard Injection")

    # Test raw key preservation on Legacy backend: U, I, W, Shift, Space, M
    test_state = {
        "buttons": {},
        "axes": {},
        "key_codes": ["KeyW", "KeyU", "KeyI", "Space", "ShiftLeft", "KeyM"],
    }
    slot.controller.apply(test_state)
    active_vks = slot.controller._down_keys
    # W=0x57, U=0x55, I=0x49, Space=0x20, LShift=0xA0, M=0x4D
    expected_vks = {0x57, 0x55, 0x49, 0x20, 0xA0, 0x4D}
    assert active_vks == expected_vks, f"Expected VKs {expected_vks}, got {active_vks}"
    print(f"  [PASS] Legacy Keyboard Injection preserved exact raw keys: {active_vks}")
    slot.controller.release_all()

    # 4. Attempt Switch to VHF Keyboard (when driver unavailable)
    # Must fail safely and keep current active backend intact!
    print("  [INFO] Attempting switch to Virtual Keyboard HID (VHF)...")
    ok_vhf = await sm.set_controller_type(1, "virtual_keyboard")
    if not ok_vhf:
        print("  [PASS] VHF switch failed safely as expected (driver not loaded)")
        assert slot.controller_type == "keyboard"
        assert isinstance(slot.controller, KeyboardInjectionBackend)
        print("  [PASS] Transactional resilience confirmed: Slot 1 retained working Keyboard backend")
    else:
        print("  [PASS] VHF driver is installed and active on host!")
        assert isinstance(slot.controller, VirtualKeyboardHIDBackend)

    # 5. Switch Back to Xbox 360
    ok = await sm.set_controller_type(1, "xbox360")
    assert ok is True
    assert isinstance(slot.controller, Xbox360Backend)
    print("  [PASS] Switched Slot 1 back to Xbox 360")

    await sm.stop()
    print("  >>> BACKEND TRANSITION TESTS COMPLETED SUCCESSFULLY! <<<\n")


if __name__ == "__main__":
    asyncio.run(run_backend_transition_test())
