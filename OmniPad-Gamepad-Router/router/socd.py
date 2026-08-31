"""
Simultaneous Opposing Cardinal Directions (SOCD) Cleaner.
Essential for fighting games (Street Fighter 6, Tekken 8, Guilty Gear, etc.).
Prevents conflicting inputs like Left+Right or Down+Up from creating illegal/unintended states.
"""

from enum import Enum
from typing import Dict, Tuple, Any

class SOCDMode(str, Enum):
    NEUTRAL = "neutral"          # Left + Right = Neutral (0), Down + Up = Neutral (0) [Capcom Pro Tour / EVO standard]
    UP_PRIORITY = "up_priority"  # Left + Right = Neutral (0), Down + Up = Up [Classic Hitbox / Leverless]
    LAST_WIN = "last_win"        # The most recently pressed direction takes priority
    RAW = "raw"                  # No filtering applied

class SOCDCleaner:
    def __init__(self, mode: SOCDMode = SOCDMode.NEUTRAL):
        self.mode = mode
        self._last_horizontal: str = "" # "left" or "right"
        self._last_vertical: str = ""   # "up" or "down"

    def clean_buttons(self, buttons: Dict[str, bool]) -> Dict[str, bool]:
        """
        Cleans DPAD buttons according to the current SOCD mode.
        Modifies and returns the buttons dictionary.
        """
        if self.mode == SOCDMode.RAW:
            return buttons

        up = bool(buttons.get("DPAD_UP", False))
        down = bool(buttons.get("DPAD_DOWN", False))
        left = bool(buttons.get("DPAD_LEFT", False))
        right = bool(buttons.get("DPAD_RIGHT", False))

        # Track last pressed directions for LAST_WIN
        if left and not right and self._last_horizontal != "left":
            self._last_horizontal = "left"
        elif right and not left and self._last_horizontal != "right":
            self._last_horizontal = "right"
        elif not left and not right:
            self._last_horizontal = ""

        if up and not down and self._last_vertical != "up":
            self._last_vertical = "up"
        elif down and not up and self._last_vertical != "down":
            self._last_vertical = "down"
        elif not up and not down:
            self._last_vertical = ""

        # Horizontal Cleaning (Left + Right)
        if left and right:
            if self.mode == SOCDMode.LAST_WIN:
                if self._last_horizontal == "left":
                    buttons["DPAD_LEFT"] = True
                    buttons["DPAD_RIGHT"] = False
                elif self._last_horizontal == "right":
                    buttons["DPAD_LEFT"] = False
                    buttons["DPAD_RIGHT"] = True
                else:
                    buttons["DPAD_LEFT"] = False
                    buttons["DPAD_RIGHT"] = False
            else: # NEUTRAL and UP_PRIORITY both do Neutral for Left+Right
                buttons["DPAD_LEFT"] = False
                buttons["DPAD_RIGHT"] = False

        # Vertical Cleaning (Down + Up)
        if up and down:
            if self.mode == SOCDMode.UP_PRIORITY:
                buttons["DPAD_UP"] = True
                buttons["DPAD_DOWN"] = False
            elif self.mode == SOCDMode.LAST_WIN:
                if self._last_vertical == "up":
                    buttons["DPAD_UP"] = True
                    buttons["DPAD_DOWN"] = False
                elif self._last_vertical == "down":
                    buttons["DPAD_UP"] = False
                    buttons["DPAD_DOWN"] = True
                else:
                    buttons["DPAD_UP"] = False
                    buttons["DPAD_DOWN"] = False
            else: # NEUTRAL (Capcom standard: Down + Up = Neutral)
                buttons["DPAD_UP"] = False
                buttons["DPAD_DOWN"] = False

        return buttons

    def clean_stick(self, x: float, y: float, deadzone: float = 0.15) -> Tuple[float, float]:
        """
        Applies radial deadzone and normalizes analog joystick values.
        x: -1.0 (left) to 1.0 (right)
        y: -1.0 (down) to 1.0 (up)
        """
        import math
        mag = math.hypot(x, y)
        if mag < deadzone:
            return 0.0, 0.0
        
        # Scale remaining range to 0.0..1.0
        scale = (mag - deadzone) / (1.0 - deadzone) / mag
        nx = max(-1.0, min(1.0, x * scale))
        ny = max(-1.0, min(1.0, y * scale))
        return nx, ny
