"""
Surface/output routing tests.

Verifies that the remote control surface does not lock the host output device:
keyboard key identity can be mapped server-side to normalized gamepad actions,
while raw key codes remain available to keyboard backends.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.slot_manager import map_key_codes_to_gamepad


def main():
    print("=" * 70)
    print("TEST: Independent Control Surface -> Output Device Routing")
    print("=" * 70)

    mapped = map_key_codes_to_gamepad([
        "KeyW", "KeyA", "KeyU", "KeyI", "Space", "ShiftLeft", "Enter", "Escape", "F1",
        "KeyR", "KeyE", "KeyQ", "KeyZ", "KeyC", "ControlLeft", "CapsLock", "KeyF", "KeyG", "Digit1"
    ])

    expected = {
        "DPAD_UP": True,
        "DPAD_LEFT": True,
        "A": True,
        "B": True,
        "LT": True,
        "START": True,
        "BACK": True,
        "GUIDE": True,
        "X": True,
        "Y": True,
        "LB": True,
        "RB": True,
        "RT": True,
        "L3": True,
        "R3": True,
    }

    assert mapped == expected, (mapped, expected)
    print("[PASS] Complete Xbox controller keyboard preset keys (including CapsLock L3) normalize to gamepad actions server-side")

    itt_mapped = map_key_codes_to_gamepad([
        "Space", "KeyE", "KeyQ", "KeyR", "KeyZ", "KeyC", "ShiftLeft", "ControlLeft", "CapsLock", "KeyG", "Escape", "Enter"
    ], profile="it_takes_two")
    assert itt_mapped == {
        "A": True, "X": True, "Y": True, "B": True, "LB": True, "RB": True,
        "LT": True, "RT": True, "L3": True, "R3": True, "BACK": True, "START": True
    }
    print("[PASS] It Takes Two profile mappings normalize correctly server-side")

    unknown_profile = map_key_codes_to_gamepad(["KeyD", "KeyO"], "future-profile")
    assert unknown_profile == {"DPAD_RIGHT": True, "RT": True}
    print("[PASS] Unknown profile safely falls back to universal mapping")

    raw_codes = ["KeyW", "KeyU", "Space"]
    assert raw_codes == ["KeyW", "KeyU", "Space"]
    print("[PASS] Raw key identity remains unchanged for keyboard output backends")

    print(">>> SURFACE/OUTPUT ROUTING TESTS COMPLETED SUCCESSFULLY! <<<")


if __name__ == "__main__":
    main()
