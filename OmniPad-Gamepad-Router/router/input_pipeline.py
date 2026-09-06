"""Input packet fusion and normalization for routed player slots."""

from typing import Any, Dict, Mapping

from .key_mapping import map_key_codes_to_gamepad
from .socd import SOCDCleaner


def build_normalized_input_state(
    client_packets: Mapping[Any, Mapping[str, Any]],
    latest_packet: Mapping[str, Any],
    socd_cleaner: SOCDCleaner,
    deadzone: float,
) -> Dict[str, Any]:
    """Fuse active client snapshots into one backend-neutral input state."""
    input_surface = str(latest_packet.get("input_surface") or "unknown")
    mapping_profile = str(latest_packet.get("mapping_profile") or "universal")

    if len(client_packets) <= 1:
        raw_buttons = dict(latest_packet.get("buttons", {}) or {})
        raw_axes = dict(latest_packet.get("axes", {}) or {})
        raw_key_codes = [
            str(key_code) for key_code in (latest_packet.get("key_codes") or [])
        ][:64]
        keyboard_fallback_codes = [
            str(key_code)
            for key_code in (latest_packet.get("keyboard_fallback_codes") or [])
        ][:32]
    else:
        raw_buttons: Dict[str, bool] = {}
        raw_key_codes_set: set[str] = set()
        keyboard_fallback_codes_set: set[str] = set()
        raw_axes = {
            "lx": 0.0,
            "ly": 0.0,
            "rx": 0.0,
            "ry": 0.0,
            "lt": 0.0,
            "rt": 0.0,
        }

        for client_packet in client_packets.values():
            for button, value in (client_packet.get("buttons") or {}).items():
                if value:
                    raw_buttons[button] = True
            for key_code in client_packet.get("key_codes") or []:
                raw_key_codes_set.add(str(key_code))
            for key_code in client_packet.get("keyboard_fallback_codes") or []:
                keyboard_fallback_codes_set.add(str(key_code))

            client_axes = client_packet.get("axes") or {}
            for axis in ("lx", "ly", "rx", "ry"):
                client_value = float(client_axes.get(axis, 0.0) or 0.0)
                if abs(client_value) > abs(raw_axes[axis]):
                    raw_axes[axis] = client_value
            for axis in ("lt", "rt"):
                client_value = float(client_axes.get(axis, 0.0) or 0.0)
                if client_value > raw_axes[axis]:
                    raw_axes[axis] = client_value

        raw_key_codes = list(raw_key_codes_set)[:64]
        keyboard_fallback_codes = list(keyboard_fallback_codes_set)[:32]

    # Browser Keyboard mode is already resolved into backend-neutral buttons
    # and LS/RS axes. Mapping its raw key identities here a second time makes
    # camera keys perform unrelated movement/actions. Raw key_codes are still
    # retained for the physical and UMDF keyboard backends.
    if input_surface not in {"background_native", "keyboard", "hybrid"}:
        mapped_buttons = map_key_codes_to_gamepad(raw_key_codes, mapping_profile)
        for action, pressed in mapped_buttons.items():
            if pressed:
                raw_buttons[action] = True

    cleaned_buttons = socd_cleaner.clean_buttons(raw_buttons)

    lx = float(raw_axes.get("lx", 0.0) or 0.0)
    ly = float(raw_axes.get("ly", 0.0) or 0.0)
    rx = float(raw_axes.get("rx", 0.0) or 0.0)
    ry = float(raw_axes.get("ry", 0.0) or 0.0)
    lt = max(0.0, min(1.0, float(raw_axes.get("lt", 0.0) or 0.0)))
    rt = max(0.0, min(1.0, float(raw_axes.get("rt", 0.0) or 0.0)))

    # Keyboard ramping and low-sensitivity mouse input are already deliberate
    # values, so the controller deadzone must not attenuate them again.
    if input_surface in {"keyboard", "hybrid", "background_native"}:
        effective_deadzone = 0.0
    elif input_surface == "touch":
        effective_deadzone = 0.02
    else:
        effective_deadzone = deadzone
    clean_lx, clean_ly = socd_cleaner.clean_stick(lx, ly, effective_deadzone)
    clean_rx, clean_ry = socd_cleaner.clean_stick(rx, ry, effective_deadzone)

    return {
        "buttons": cleaned_buttons,
        "axes": {
            "lx": clean_lx,
            "ly": clean_ly,
            "rx": clean_rx,
            "ry": clean_ry,
            "lt": lt,
            "rt": rt,
        },
        "key_codes": raw_key_codes,
        "keyboard_fallback_codes": keyboard_fallback_codes,
        "input_surface": input_surface,
        "mapping_profile": mapping_profile,
    }
