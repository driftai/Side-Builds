import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from router.vhf_keyboard import (
    build_keyboard_report,
    dom_code_to_hid_usage,
    VHFKeyboardDevice,
    REPORT_SIZE,
    MAX_KEYS,
    IOCTL_OMNIPAD_SET_KEYBOARD_REPORT
)
from router.backends.vhf import VirtualKeyboardHIDBackend

ROOT = Path(__file__).resolve().parents[1]


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
    assert dom_code_to_hid_usage("F24") == 0x73
    assert dom_code_to_hid_usage("AudioVolumeUp") == 0x80
    assert dom_code_to_hid_usage("NumpadComma") == 0x85
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

    # Extended keyboard-page usages must fit the C descriptor's 0-255 array.
    report = build_keyboard_report(["F24", "AudioVolumeUp", "NumpadComma"])
    assert report == bytes([0x00, 0x00, 0x73, 0x80, 0x85, 0x00, 0x00, 0x00])
    print("  [PASS] 8-Byte boot keyboard report generation & modifier packing")


def test_device_contract():
    assert IOCTL_OMNIPAD_SET_KEYBOARD_REPORT == 0x0022A004
    dev, err = VHFKeyboardDevice.try_open()
    # In sandbox/environment without installed driver, try_open returns (None, err)
    if dev is None:
        print(f"  [INFO] VHF Kernel Device not currently loaded on host: {err}")
    else:
        print(f"  [PASS] VHF Kernel Device successfully opened at {dev.device_path}")
        dev.close()
    print("  [PASS] VHF device contract and IOCTL alignment")


def test_backend_lifecycle():
    class FakeDevice:
        def __init__(self):
            self.reports = []
            self.release_count = 0
            self.closed = False

        def submit_report(self, report):
            self.reports.append(report)

        def release_all(self):
            self.release_count += 1

        def close(self):
            self.closed = True

    device = FakeDevice()
    backend = VirtualKeyboardHIDBackend.__new__(VirtualKeyboardHIDBackend)
    backend.slot_id = 1
    backend.device = device
    backend.last_report = bytes(8)

    backend.apply({"key_codes": ["ShiftLeft", "KeyW"]})
    assert device.reports == [bytes([0x02, 0x00, 0x1A, 0, 0, 0, 0, 0])]
    assert backend.last_report == device.reports[-1]

    backend.release_all()
    assert device.release_count == 1
    assert backend.last_report == bytes(8)

    backend.close()
    assert device.closed is True
    assert backend.device is None
    print("  [PASS] VHF backend apply, release, and close lifecycle")


def test_driver_source_contract():
    driver = (ROOT / "drivers" / "virtual-keyboard" / "OmniPadVirtualKeyboard.c").read_text(encoding="utf-8")
    header = (ROOT / "drivers" / "virtual-keyboard" / "OmniPadVirtualKeyboard.h").read_text(encoding="utf-8")
    inf = (ROOT / "drivers" / "virtual-keyboard" / "OmniPadVirtualKeyboard.inf").read_text(encoding="utf-8")
    project = (ROOT / "drivers" / "virtual-keyboard" / "OmniPadVirtualKeyboard.vcxproj").read_text(encoding="utf-8")
    build = (ROOT / "drivers" / "virtual-keyboard" / "build-driver.ps1").read_text(encoding="utf-8")
    build_bat = (ROOT / "drivers" / "virtual-keyboard" / "build-driver.bat").read_text(encoding="utf-8")
    install = (ROOT / "drivers" / "virtual-keyboard" / "install-driver.ps1").read_text(encoding="utf-8")
    build_notes = (ROOT / "drivers" / "virtual-keyboard" / "BUILD.md").read_text(encoding="utf-8")
    readme = (ROOT / "drivers" / "virtual-keyboard" / "README.md").read_text(encoding="utf-8")
    slots = (ROOT / "router" / "slot_manager.py").read_text(encoding="utf-8")
    backend = (ROOT / "router" / "backends" / "vhf.py").read_text(encoding="utf-8")
    router_init = (ROOT / "router" / "__init__.py").read_text(encoding="utf-8")

    assert "0x26, 0xFF, 0x00" in driver
    assert "0x29, 0xFF" in driver
    assert "WdfDeviceInitSetExclusive(DeviceInit, TRUE)" in driver
    assert "OmniPadEvtFileCleanup" in driver
    assert "(A;;GA;;;BU)" not in driver
    assert "FILE_WRITE_DATA" in header and "FILE_ANY_ACCESS" not in header
    assert "AddService = OmniPadVirtualKeyboard,0x00000002" in inf
    assert '"vhf"' in inf and "MsHidKmdf.inf" not in inf
    assert "VhfKm.lib" in project
    assert "<WarningLevel>Level4</WarningLevel>" in project
    assert '<FilesToPackage Include="$(TargetPath)"' in project
    assert "OmniPadVirtualKeyboard.vcxproj" in build and "OmniPadVirtualKeyboard.sln" not in build
    assert "Bin\\amd64\\MSBuild.exe" in build
    assert "build-driver.ps1" in build_bat and "OmniPadVirtualKeyboard.sln" not in build_bat
    assert "x64\\Debug\\OmniPadVirtualKeyboard" in install
    assert "Get-AuthenticodeSignature" in install
    assert "signature.Status -ne 'Valid'" in install
    assert "OmniPadVirtualKeyboard.sln" not in build_notes
    assert "OmniPadVirtualKeyboard.sln" not in readme
    assert '{"keyboard_target", "keyboard", "virtual_keyboard"}' in slots
    assert "VHFKeyboardDevice.try_open()" in backend
    assert "class VirtualKeyboardHIDBackend" not in router_init
    print("  [PASS] Driver descriptor, access, INF, build, cleanup, and target-gating contracts")


def main() -> None:
    print("\n" + "=" * 60)
    print("  TEST: OmniPad VHF Virtual Keyboard Bridge")
    print("=" * 60)
    test_dom_code_mapping()
    test_report_building()
    test_device_contract()
    test_backend_lifecycle()
    test_driver_source_contract()
    print("  >>> VHF KEYBOARD TESTS COMPLETED SUCCESSFULLY! <<<\n")


if __name__ == "__main__":
    main()

