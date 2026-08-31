import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from router.vhf_keyboard import (
    build_keyboard_report,
    dom_code_to_hid_usage,
    VHFKeyboardDevice,
    REPORT_SIZE,
    MAX_KEYS,
    IOCTL_OMNIPAD_SET_KEYBOARD_REPORT
)


def test_dom_code_mapping():
    # Common fighting game & WASD keys
    assert dom_code_to_hid_usage("KeyW") == 0x1A
    assert dom_code_to_hid_usage("KeyA") == 0x04
    assert dom_code_to_hid_usage("KeyS") == 0x16
    assert dom_code_to_hid_usage("KeyD") == 0x07
    assert dom_code_to_hid_usage("KeyU") == 0x18
    assert dom_code_to_hid_usage("KeyI") == 0x0C
    assert dom_code_to_hid_usage("KeyO") == 0x12
    assert dom_code_to_hid_usage("KeyJ") == 0x0D
    assert dom_code_to_hid_usage("KeyK") == 0x0E
    assert dom_code_to_hid_usage("KeyL") == 0x0F
    assert dom_code_to_hid_usage("Space") == 0x2C
    assert dom_code_to_hid_usage("Enter") == 0x28
    assert dom_code_to_hid_usage("Escape") == 0x29
    assert dom_code_to_hid_usage("ArrowUp") == 0x52
    assert dom_code_to_hid_usage("ArrowDown") == 0x51
    assert dom_code_to_hid_usage("ArrowLeft") == 0x50
    assert dom_code_to_hid_usage("ArrowRight") == 0x4F
    assert dom_code_to_hid_usage("ShiftLeft") == 0xE1
    assert dom_code_to_hid_usage("ControlLeft") == 0xE0
    assert dom_code_to_hid_usage("AltLeft") == 0xE2
    assert dom_code_to_hid_usage("MetaLeft") == 0xE3
    assert dom_code_to_hid_usage("DefinitelyNotAKey") is None
    print("  [PASS] DOM KeyboardEvent.code -> USB HID usage code mapping")


def test_report_building():
    # Empty report
    empty = build_keyboard_report([])
    assert empty == bytes(8)
    assert len(empty) == REPORT_SIZE

    # U + I + O -> HID usages 0x18, 0x0C, 0x12
    report = build_keyboard_report(["KeyU", "KeyI", "KeyO"])
    assert report == bytes([0x00, 0x00, 0x18, 0x0C, 0x12, 0x00, 0x00, 0x00])

    # Left shift (mod bit 1 -> 0x02) + U (0x18)
    report = build_keyboard_report(["ShiftLeft", "KeyU"])
    assert report[0] == 0x02
    assert report[1] == 0x00
    assert report[2] == 0x18
    assert report[3:] == bytes(5)

    # Combined modifiers: CtrlLeft (0x01) + AltLeft (0x04) + ShiftRight (0x20) = 0x25
    report = build_keyboard_report(["ControlLeft", "AltLeft", "ShiftRight", "KeyW", "Space"])
    assert report[0] == 0x25
    assert report[1] == 0x00
    assert report[2] == 0x1A
    assert report[3] == 0x2C
    assert report[4:] == bytes(4)

    # Duplicate key suppression
    report = build_keyboard_report(["KeyU", "KeyU", "KeyU"])
    assert report == bytes([0x00, 0x00, 0x18, 0x00, 0x00, 0x00, 0x00, 0x00])

    # 6-key rollover cap (Q W E R T Y U -> exactly 6 keys stored)
    report = build_keyboard_report([f"Key{x}" for x in "QWERTYU"])
    assert len(report) == 8
    assert report[2:8] == bytes([0x14, 0x1A, 0x08, 0x15, 0x17, 0x1C])
    print("  [PASS] 8-Byte boot keyboard report generation & modifier packing")


def test_device_contract():
    assert IOCTL_OMNIPAD_SET_KEYBOARD_REPORT == 0x00222004
    dev, err = VHFKeyboardDevice.try_open()
    # In sandbox/environment without installed driver, try_open returns (None, err)
    if dev is None:
        print(f"  [INFO] VHF Kernel Device not currently loaded on host: {err}")
    else:
        print(f"  [PASS] VHF Kernel Device successfully opened at {dev.device_path}")
        dev.close()
    print("  [PASS] VHF device contract and IOCTL alignment")


def main() -> None:
    print("\n" + "=" * 60)
    print("  TEST: OmniPad VHF Virtual Keyboard Bridge")
    print("=" * 60)
    test_dom_code_mapping()
    test_report_building()
    test_device_contract()
    print("  >>> VHF KEYBOARD TESTS COMPLETED SUCCESSFULLY! <<<\n")


if __name__ == "__main__":
    main()

