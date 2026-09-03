import sys
import pathlib
import ctypes

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.vhf_keyboard import build_keyboard_report, _DOM_CODE_TO_HID
from router.controller import _dom_code_to_vk
from router.backends import keyboard as keyboard_backend


def test_client_virtual_keyboard_structures():
    play_js = (ROOT / "static" / "js" / "play.js").read_text(encoding="utf-8")
    layouts_js = (ROOT / "static" / "js" / "keyboard_layouts.js").read_text(encoding="utf-8")
    vk_js = (ROOT / "static" / "js" / "virtual_keyboard.js").read_text(encoding="utf-8")
    html_text = (ROOT / "static" / "play.html").read_text(encoding="utf-8")

    # Verify device tabs & layout options
    assert "data-mode=\"keyboard\"" in html_text
    assert "data-mode=\"gamepad\"" in html_text
    assert "data-mode=\"touch\"" in html_text
    assert "vk-chassis" in html_text
    assert "keyboard_layouts.js" in html_text
    assert "virtual_keyboard.js" in html_text

    # Verify JS layouts and pointer events
    assert "KEYBOARD_LAYOUTS" in layouts_js
    assert "wasd_fighter" in layouts_js
    assert "standard_full" in layouts_js
    assert "arrow_numpad" in layouts_js
    assert "compact_60" in layouts_js
    assert "pointerdown" in vk_js
    assert "pointerup" in vk_js
    assert "activeKeys.add" in vk_js
    assert "key_codes:" in play_js


def test_end_to_end_u_i_o_preservation():
    """Verify that clicking/pressing U, I, O on virtual or physical keyboard
    produces exact KeyU, KeyI, KeyO codes that translate directly into HID usages
    without gamepad button translation."""
    
    # 1. DOM Codes
    test_codes = ["KeyU", "KeyI", "KeyO", "KeyW", "ShiftLeft", "Space", "KeyM"]
    
    # 2. USB HID Page 0x07 translations
    assert _DOM_CODE_TO_HID["KeyU"] == 0x18  # USB HID Usage for 'u'
    assert _DOM_CODE_TO_HID["KeyI"] == 0x0C  # USB HID Usage for 'i'
    assert _DOM_CODE_TO_HID["KeyO"] == 0x12  # USB HID Usage for 'o'
    assert _DOM_CODE_TO_HID["KeyW"] == 0x1A  # USB HID Usage for 'w'
    assert _DOM_CODE_TO_HID["KeyM"] == 0x10  # USB HID Usage for 'm'
    assert _DOM_CODE_TO_HID["Space"] == 0x2C  # Spacebar
    assert _DOM_CODE_TO_HID["ShiftLeft"] == 0xE1  # Modifier Left Shift

    # 3. Report Packing
    report = build_keyboard_report(test_codes)
    assert len(report) == 8
    # Modifier byte should have Left Shift bit set (0x02)
    assert report[0] == 0x02
    # Reserved byte
    assert report[1] == 0x00
    # Next 6 bytes contain the non-modifier keys in report
    active_usages = set(report[2:])
    active_usages.discard(0x00)
    assert 0x18 in active_usages  # KeyU
    assert 0x0C in active_usages  # KeyI
    assert 0x12 in active_usages  # KeyO
    assert 0x1A in active_usages  # KeyW
    assert 0x10 in active_usages  # KeyM
    assert 0x2C in active_usages  # Space

    # 4. Windows VK codes for SendInput fallback
    assert _dom_code_to_vk("KeyU") == 0x55  # VK_U
    assert _dom_code_to_vk("KeyI") == 0x49  # VK_I
    assert _dom_code_to_vk("KeyO") == 0x4F  # VK_O
    assert _dom_code_to_vk("KeyW") == 0x57  # VK_W
    assert _dom_code_to_vk("KeyM") == 0x4D  # VK_M
    assert _dom_code_to_vk("ShiftLeft") == 0xA0  # VK_LSHIFT
    assert _dom_code_to_vk("Space") == 0x20  # VK_SPACE


def test_sendinput_uses_scan_codes_and_retries_failed_transitions():
    if not keyboard_backend.IS_WINDOWS:
        return

    captured = []
    fail_first = True

    def fake_send_input(count, input_pointer, size):
        nonlocal fail_first
        assert count == 1
        assert size == ctypes.sizeof(keyboard_backend._INPUT)
        event = ctypes.cast(
            input_pointer, ctypes.POINTER(keyboard_backend._INPUT)
        ).contents
        captured.append((event.ki.wVk, event.ki.wScan, event.ki.dwFlags))
        if fail_first:
            fail_first = False
            return 0
        return 1

    original_send_input = keyboard_backend._SendInput
    keyboard_backend._SendInput = fake_send_input
    try:
        backend = keyboard_backend.KeyboardInjectionBackend.__new__(
            keyboard_backend.KeyboardInjectionBackend
        )
        backend.slot_id = 1
        backend.keymap = {}
        backend._down_keys = set()
        backend._sent_keys = set()

        backend.apply({"key_codes": ["KeyW"]})
        assert backend._down_keys == {0x57}
        assert backend._sent_keys == set(), "failed keydown must remain retryable"

        backend.apply({"key_codes": ["KeyW"]})
        assert backend._down_keys == {0x57}
        assert backend._sent_keys == {0x57}
        down_vk, down_scan, down_flags = captured[-1]
        assert down_vk == 0
        assert down_scan == 0x11
        assert down_flags & keyboard_backend._KEYEVENTF_SCANCODE
        assert not down_flags & keyboard_backend._KEYEVENTF_KEYUP

        backend.release_all()
        assert backend._down_keys == set()
        assert backend._sent_keys == set()
        up_vk, up_scan, up_flags = captured[-1]
        assert up_vk == 0
        assert up_scan == 0x11
        assert up_flags & keyboard_backend._KEYEVENTF_SCANCODE
        assert up_flags & keyboard_backend._KEYEVENTF_KEYUP

        extended = keyboard_backend._make_keyboard_input(0x26, True)
        assert extended.ki.dwFlags & keyboard_backend._KEYEVENTF_SCANCODE
        assert extended.ki.dwFlags & keyboard_backend._KEYEVENTF_EXTENDEDKEY
    finally:
        keyboard_backend._SendInput = original_send_input


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  TEST: Keyboard Bridge & Interactive Virtual Keyboard")
    print("=" * 60)
    test_client_virtual_keyboard_structures()
    print("  [PASS] Web client transmits raw KeyboardEvent.code list & defines virtual keyboard")
    test_end_to_end_u_i_o_preservation()
    print("  [PASS] End-to-end key identity preservation verified (KeyU, KeyI, KeyO, KeyW, Shift, M, Space)")
    test_sendinput_uses_scan_codes_and_retries_failed_transitions()
    print("  [PASS] SendInput uses scan codes and retries failed key transitions")
    print("  >>> KEYBOARD BRIDGE TESTS COMPLETED SUCCESSFULLY! <<<\n")

