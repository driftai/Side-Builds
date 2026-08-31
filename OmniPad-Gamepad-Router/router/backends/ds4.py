"""
Virtual DualShock 4 Controller Backend (ViGEmBus / DirectInput).
"""

import logging
from typing import Dict, Any, Set

from .base import BaseController, VIGEM_AVAILABLE

logger = logging.getLogger("OmniPad.Controller.DS4")

try:
    import vgamepad as vg
except Exception:
    vg = None


class DualShock4Backend(BaseController):
    """Virtual DualShock 4 Controller powered by ViGEmBus."""
    backend_id = "ds4"
    display_name = "DualShock 4 Controller (DirectInput / DS4)"

    _BUTTON_MAP = {
        "A": vg.DS4_BUTTONS.DS4_BUTTON_CROSS if vg else 0,       # Cross
        "B": vg.DS4_BUTTONS.DS4_BUTTON_CIRCLE if vg else 0,      # Circle
        "X": vg.DS4_BUTTONS.DS4_BUTTON_SQUARE if vg else 0,      # Square
        "Y": vg.DS4_BUTTONS.DS4_BUTTON_TRIANGLE if vg else 0,    # Triangle
        "LB": vg.DS4_BUTTONS.DS4_BUTTON_SHOULDER_LEFT if vg else 0,
        "RB": vg.DS4_BUTTONS.DS4_BUTTON_SHOULDER_RIGHT if vg else 0,
        "BACK": vg.DS4_BUTTONS.DS4_BUTTON_SHARE if vg else 0,
        "SELECT": vg.DS4_BUTTONS.DS4_BUTTON_SHARE if vg else 0,
        "START": vg.DS4_BUTTONS.DS4_BUTTON_OPTIONS if vg else 0,
        "L3": vg.DS4_BUTTONS.DS4_BUTTON_THUMB_LEFT if vg else 0,
        "LS": vg.DS4_BUTTONS.DS4_BUTTON_THUMB_LEFT if vg else 0,
        "R3": vg.DS4_BUTTONS.DS4_BUTTON_THUMB_RIGHT if vg else 0,
        "RS": vg.DS4_BUTTONS.DS4_BUTTON_THUMB_RIGHT if vg else 0,
        "TOUCHPAD": vg.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_TOUCHPAD if vg else 0,
        "GUIDE": vg.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_PS if vg else 0,
    }

    _DPAD_MAP = {
        # (UP, DOWN, LEFT, RIGHT) -> DS4_DPAD_DIRECTIONS
        (False, False, False, False): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NONE if vg else 0,
        (True, False, False, False): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTH if vg else 0,
        (True, False, False, True): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHEAST if vg else 0,
        (False, False, False, True): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_EAST if vg else 0,
        (False, True, False, True): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTHEAST if vg else 0,
        (False, True, False, False): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTH if vg else 0,
        (False, True, True, False): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTHWEST if vg else 0,
        (False, False, True, False): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_WEST if vg else 0,
        (True, False, True, False): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHWEST if vg else 0,
    }

    def __init__(self, slot_id: int):
        if not VIGEM_AVAILABLE or vg is None:
            raise RuntimeError("ViGEmBus / vgamepad driver is not available.")
        self.slot_id = slot_id
        self.pad = vg.VDS4Gamepad()
        self._pressed_buttons: Set[str] = set()
        logger.info("[Slot %d] Created virtual DualShock 4 controller", self.slot_id)

    def apply(self, state: Dict[str, Any]) -> None:
        buttons = state.get("buttons", {})
        axes = state.get("axes", {})

        # Process main buttons
        for name, button_code in self._BUTTON_MAP.items():
            if not button_code:
                continue
            is_down = bool(buttons.get(name, False))
            was_down = name in self._pressed_buttons

            if is_down and not was_down:
                if name in ("TOUCHPAD", "GUIDE"):
                    self.pad.press_special_button(special_button=button_code)
                else:
                    self.pad.press_button(button=button_code)
                self._pressed_buttons.add(name)
            elif not is_down and was_down:
                if name in ("TOUCHPAD", "GUIDE"):
                    self.pad.release_special_button(special_button=button_code)
                else:
                    self.pad.release_button(button=button_code)
                self._pressed_buttons.discard(name)

        # Process DS4 D-Pad hat direction
        up = bool(buttons.get("DPAD_UP", False))
        down = bool(buttons.get("DPAD_DOWN", False))
        left = bool(buttons.get("DPAD_LEFT", False))
        right = bool(buttons.get("DPAD_RIGHT", False))
        dpad_dir = self._DPAD_MAP.get((up, down, left, right), vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NONE if vg else 0)
        self.pad.directional_pad(direction=dpad_dir)

        # Process analog sticks (-1.0 to 1.0)
        lx = max(-1.0, min(1.0, float(axes.get("lx", 0.0) or 0.0)))
        ly = max(-1.0, min(1.0, float(axes.get("ly", 0.0) or 0.0)))
        rx = max(-1.0, min(1.0, float(axes.get("rx", 0.0) or 0.0)))
        ry = max(-1.0, min(1.0, float(axes.get("ry", 0.0) or 0.0)))

        self.pad.left_joystick_float(x_value_float=lx, y_value_float=ly)
        self.pad.right_joystick_float(x_value_float=rx, y_value_float=ry)

        # Process analog triggers (0.0 to 1.0)
        lt = max(0.0, min(1.0, float(axes.get("lt", 0.0) or (1.0 if buttons.get("LT") else 0.0))))
        rt = max(0.0, min(1.0, float(axes.get("rt", 0.0) or (1.0 if buttons.get("RT") else 0.0))))

        self.pad.left_trigger_float(value_float=lt)
        self.pad.right_trigger_float(value_float=rt)

        self.pad.update()

    def release_all(self) -> None:
        try:
            self.pad.reset()
            self.pad.update()
            self._pressed_buttons.clear()
            logger.debug("[Slot %d] DS4 released all inputs", self.slot_id)
        except Exception as e:
            logger.error("[Slot %d] Error releasing DS4 inputs: %s", self.slot_id, e)

    def close(self) -> None:
        self.release_all()
        try:
            del self.pad
        except Exception:
            pass
        logger.info("[Slot %d] DS4 controller disconnected", self.slot_id)
