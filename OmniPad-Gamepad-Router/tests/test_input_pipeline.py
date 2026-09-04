"""Direct, low-noise contract tests for input fusion and normalization."""

import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.input_pipeline import build_normalized_input_state
from router.socd import SOCDCleaner, SOCDMode


def normalize(client_packets, latest_packet, deadzone=0.15):
    return build_normalized_input_state(
        client_packets,
        latest_packet,
        SOCDCleaner(SOCDMode.NEUTRAL),
        deadzone,
    )


def test_single_keyboard_packet_uses_resolved_state():
    packet = {
        "input_surface": "keyboard",
        "mapping_profile": "universal",
        "buttons": {"A": True},
        "axes": {"ly": 0.35},
        "key_codes": ["KeyW", "Space"],
    }
    state = normalize({"client": packet}, packet)

    assert state["buttons"]["A"] is True
    assert "DPAD_UP" not in state["buttons"]
    assert "BACK" not in state["buttons"]
    assert state["axes"]["lx"] == 0.0
    assert state["axes"]["ly"] == 0.35
    assert state["key_codes"] == ["KeyW", "Space"]
    assert state["input_surface"] == "keyboard"
    assert state["mapping_profile"] == "universal"


def test_keyboard_camera_key_does_not_cross_talk_to_movement():
    packet = {
        "input_surface": "keyboard",
        "mapping_profile": "arrow_keys_player2",
        "buttons": {},
        "axes": {"ry": 0.45},
        "key_codes": ["ArrowUp"],
    }
    state = normalize({"client": packet}, packet)

    assert state["buttons"] == {}
    assert state["axes"]["lx"] == 0.0
    assert state["axes"]["ly"] == 0.0
    assert state["axes"]["rx"] == 0.0
    assert state["axes"]["ry"] == 0.45


def test_keyboard_dpad_button_does_not_become_left_stick():
    packet = {
        "input_surface": "keyboard",
        "mapping_profile": "universal",
        "buttons": {"DPAD_UP": True},
        "axes": {},
        "key_codes": ["Digit1"],
    }
    state = normalize({"client": packet}, packet)

    assert state["buttons"]["DPAD_UP"] is True
    assert state["axes"]["lx"] == 0.0
    assert state["axes"]["ly"] == 0.0


def test_non_keyboard_surface_can_use_host_profile_mapping():
    packet = {
        "input_surface": "gamepad",
        "mapping_profile": "universal",
        "buttons": {},
        "axes": {},
        "key_codes": ["KeyW", "Space"],
    }
    state = normalize({"client": packet}, packet)

    assert state["buttons"]["DPAD_UP"] is True
    assert state["buttons"]["A"] is True


def test_background_native_does_not_remap_keys():
    packet = {
        "input_surface": "background_native",
        "buttons": {"X": True},
        "axes": {},
        "key_codes": ["Space"],
    }
    state = normalize({"client": packet}, packet)

    assert state["buttons"]["X"] is True
    assert "A" not in state["buttons"]
    assert state["key_codes"] == ["Space"]


def test_multi_client_fusion():
    first = {
        "input_surface": "gamepad",
        "buttons": {"A": True},
        "axes": {"lx": 0.4, "rt": 0.2},
        "key_codes": ["KeyU"],
    }
    latest = {
        "input_surface": "gamepad",
        "mapping_profile": "universal",
        "buttons": {"B": True},
        "axes": {"lx": -0.8, "rt": 0.7},
        "key_codes": ["KeyI"],
    }
    state = normalize({"first": first, "latest": latest}, latest, deadzone=0.0)

    assert state["buttons"]["A"] is True
    assert state["buttons"]["B"] is True
    assert set(state["key_codes"]) == {"KeyU", "KeyI"}
    assert state["axes"]["lx"] == -0.8
    assert state["axes"]["rt"] == 0.7


def test_surface_deadzone_and_socd_contracts():
    touch = {
        "input_surface": "touch",
        "buttons": {},
        "axes": {"lx": 0.03},
        "key_codes": [],
    }
    gamepad = {**touch, "input_surface": "gamepad"}
    opposing = {
        "input_surface": "keyboard",
        "buttons": {
            "DPAD_UP": True, "DPAD_DOWN": True,
            "DPAD_LEFT": True, "DPAD_RIGHT": True,
        },
        "axes": {},
        "key_codes": ["KeyW", "KeyS", "KeyA", "KeyD"],
    }

    assert normalize({"touch": touch}, touch)["axes"]["lx"] > 0.0
    assert normalize({"gamepad": gamepad}, gamepad)["axes"]["lx"] == 0.0

    state = normalize({"keyboard": opposing}, opposing)
    assert state["buttons"]["DPAD_UP"] is False
    assert state["buttons"]["DPAD_DOWN"] is False
    assert state["buttons"]["DPAD_LEFT"] is False
    assert state["buttons"]["DPAD_RIGHT"] is False
    assert state["axes"]["lx"] == 0.0
    assert state["axes"]["ly"] == 0.0


def main():
    tests = (
        test_single_keyboard_packet_uses_resolved_state,
        test_keyboard_camera_key_does_not_cross_talk_to_movement,
        test_keyboard_dpad_button_does_not_become_left_stick,
        test_non_keyboard_surface_can_use_host_profile_mapping,
        test_background_native_does_not_remap_keys,
        test_multi_client_fusion,
        test_surface_deadzone_and_socd_contracts,
    )
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    print(f"Input pipeline tests passed ({len(tests)}/{len(tests)}).")


if __name__ == "__main__":
    main()
