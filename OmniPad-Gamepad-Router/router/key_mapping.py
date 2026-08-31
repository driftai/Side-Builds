"""
Key-to-Gamepad Normalization and Profile Action Mappings.
Maps browser keyboard control surfaces to normalized gamepad actions on the host.
"""

from typing import Dict, List

UNIVERSAL_KEY_TO_GAMEPAD: Dict[str, str] = {
    # Directional / D-pad
    "KeyW": "DPAD_UP", "KeyS": "DPAD_DOWN",
    "KeyA": "DPAD_LEFT", "KeyD": "DPAD_RIGHT",
    "ArrowUp": "DPAD_UP", "ArrowDown": "DPAD_DOWN",
    "ArrowLeft": "DPAD_LEFT", "ArrowRight": "DPAD_RIGHT",
    "Digit1": "DPAD_UP", "Digit2": "DPAD_DOWN",
    "Digit3": "DPAD_LEFT", "Digit4": "DPAD_RIGHT",

    # Action buttons
    "Space": "A",
    "KeyU": "A",
    "KeyR": "B",
    "KeyI": "B",
    "KeyE": "X",
    "KeyJ": "X",
    "KeyQ": "Y",
    "KeyK": "Y",

    # Bumpers & Triggers
    "KeyZ": "LB",
    "KeyC": "RB",
    "KeyL": "RB",
    "ShiftLeft": "LT",
    "ShiftRight": "LT",
    "ControlLeft": "RT",
    "ControlRight": "RT",
    "KeyO": "RT",

    # Stick clicks & Menu buttons
    "CapsLock": "L3",
    "KeyF": "L3",
    "KeyG": "R3",
    "Enter": "START", "NumpadEnter": "START",
    "Backspace": "BACK", "Escape": "BACK",
    "F1": "GUIDE",
}

PROFILE_KEY_TO_GAMEPAD: Dict[str, Dict[str, str]] = {
    "it_takes_two": {
        **UNIVERSAL_KEY_TO_GAMEPAD,
        "Space": "A",          # Jump
        "KeyE": "X",           # Dash / Action
        "KeyQ": "Y",           # Interact / Secondary Action
        "KeyR": "B",           # Cancel
        "KeyZ": "LB",          # Ability
        "KeyC": "RB",          # Rope Grapple
        "ShiftLeft": "LT",     # Ground Pound / Crouch
        "ShiftRight": "LT",
        "ControlLeft": "RT",   # Tool / Action
        "ControlRight": "RT",
        "CapsLock": "L3",      # Sprint
        "KeyF": "L3",
        "KeyG": "R3",
    },
    "street_fighter_6": {
        **UNIVERSAL_KEY_TO_GAMEPAD,
        "KeyJ": "X", "KeyK": "Y", "KeyL": "RB",
        "KeyU": "A", "KeyI": "B", "KeyO": "RT",
        "Space": "LB", "ShiftLeft": "LT",
    },
    "tekken_8": {
        **UNIVERSAL_KEY_TO_GAMEPAD,
        "KeyJ": "X", "KeyI": "Y", "KeyK": "A", "KeyO": "B",
        "KeyU": "RB", "KeyL": "RT", "Space": "LB", "ShiftLeft": "LT",
    }
}


def map_key_codes_to_gamepad(key_codes: List[str], profile: str = "universal") -> Dict[str, bool]:
    """Map a keyboard control surface to normalized gamepad actions.

    This is deliberately server-side so the remote surface does not dictate the
    host output device.
    """
    keymap = PROFILE_KEY_TO_GAMEPAD.get(str(profile).lower(), UNIVERSAL_KEY_TO_GAMEPAD)
    mapped: Dict[str, bool] = {}
    for code in key_codes or []:
        action = keymap.get(str(code))
        if action:
            mapped[action] = True
    return mapped
