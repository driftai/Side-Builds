"""
Virtual Xbox 360 Controller Backend (ViGEmBus / XInput).
"""

import logging
from typing import Dict, Any, Set

from .base import BaseController, VIGEM_AVAILABLE

logger = logging.getLogger("OmniPad.Controller.Xbox360")

try:
    import vgamepad as vg
except Exception:
    vg = None


class Xbox360Backend(BaseController):
    """Virtual Xbox 360 Controller powered by ViGEmBus."""
    backend_id = "xbox360"
    display_name = "Xbox 360 Controller (XInput)"

    _BUTTON_MAP = {
        "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_A if vg else 0,
        "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_B if vg else 0,
        "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_X if vg else 0,
        "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y if vg else 0,
        "LB": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER if vg else 0,
        "RB": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER if vg else 0,
        "BACK": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK if vg else 0,
        "SELECT": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK if vg else 0,
        "START": vg.XUSB_BUTTON.XUSB_GAMEPAD_START if vg else 0,
        "L3": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB if vg else 0,
        "LS": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB if vg else 0,
        "R3": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB if vg else 0,
        "RS": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB if vg else 0,
        "DPAD_UP": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP if vg else 0,
        "DPAD_DOWN": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN if vg else 0,
        "DPAD_LEFT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT if vg else 0,
        "DPAD_RIGHT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT if vg else 0,
        "GUIDE": vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE if vg else 0,
    }

    def __init__(self, slot_id: int):
        if not VIGEM_AVAILABLE or vg is None:
            raise RuntimeError("ViGEmBus / vgamepad driver is not available.")
        self.slot_id = slot_id
        self.pad = vg.VX360Gamepad()
        self._pressed_buttons: Set[str] = set()
        logger.info("[Slot %d] Created virtual Xbox 360 controller", self.slot_id)

    def apply(self, state: Dict[str, Any]) -> None:
        buttons = state.get("buttons", {})
        axes = state.get("axes", {})

        # Process digital buttons
        for name, button_code in self._BUTTON_MAP.items():
            if not button_code:
                continue
            is_down = bool(buttons.get(name, False))
            was_down = name in self._pressed_buttons

            if is_down and not was_down:
                self.pad.press_button(button=button_code)
                self._pressed_buttons.add(name)
            elif not is_down and was_down:
                self.pad.release_button(button=button_code)
                self._pressed_buttons.discard(name)

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
            logger.debug("[Slot %d] Xbox 360 released all inputs", self.slot_id)
        except Exception as e:
            logger.error("[Slot %d] Error releasing inputs: %s", self.slot_id, e)

    def close(self) -> None:
        self.release_all()
        try:
            del self.pad
        except Exception:
            pass
        logger.info("[Slot %d] Xbox 360 controller disconnected", self.slot_id)
