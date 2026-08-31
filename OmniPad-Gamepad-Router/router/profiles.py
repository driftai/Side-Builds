"""
Controller & Keyboard Mapping Profiles.
Includes pre-configured profiles for Street Fighter 6, Tekken 8, Platform Fighters, Retro Emulators,
and customizable key-to-button remapping.
"""

import json
import os
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class Profile(BaseModel):
    id: str
    name: str
    category: str # "fighting", "platform", "retro", "custom"
    description: str
    socd_mode: str = "neutral"
    deadzone: float = 0.15
    # Keyboard Key -> Gamepad Button mapping
    # Key codes use standard JavaScript KeyboardEvent.code (e.g. 'KeyW', 'KeyA', 'KeyJ', 'Space')
    keymap: Dict[str, str] = Field(default_factory=dict)
    # Extra button aliases or labels for UI
    labels: Dict[str, str] = Field(default_factory=dict)

# Built-in Profiles
BUILTIN_PROFILES: List[Profile] = [
    Profile(
        id="street_fighter_6",
        name="Street Fighter 6 (6-Button Layout)",
        category="fighting",
        description="Standard 6-button arcade / hitbox layout. WASD directions, J/K/L for punches, U/I/O for kicks, Space for Parry, Shift for Drive Impact.",
        socd_mode="neutral",
        deadzone=0.15,
        keymap={
            "KeyW": "DPAD_UP",
            "KeyS": "DPAD_DOWN",
            "KeyA": "DPAD_LEFT",
            "KeyD": "DPAD_RIGHT",
            "KeyJ": "X",          # Light Punch (Square / X)
            "KeyK": "Y",          # Medium Punch (Triangle / Y)
            "KeyL": "RB",         # Heavy Punch (R1 / RB)
            "KeyU": "A",          # Light Kick (Cross / A)
            "KeyI": "B",          # Medium Kick (Circle / B)
            "KeyO": "RT",         # Heavy Kick (R2 / RT)
            "Space": "LB",        # Drive Parry (L1 / LB)
            "ShiftLeft": "LT",    # Drive Impact (L2 / LT)
            "Enter": "START",
            "Backspace": "BACK",
            "Digit1": "LS",       # Taunt / L3
            "Digit2": "RS",       # Taunt / R3
        },
        labels={
            "X": "Light Punch (LP)",
            "Y": "Medium Punch (MP)",
            "RB": "Heavy Punch (HP)",
            "A": "Light Kick (LK)",
            "B": "Medium Kick (MK)",
            "RT": "Heavy Kick (HK)",
            "LB": "Drive Parry",
            "LT": "Drive Impact",
        }
    ),
    Profile(
        id="tekken_8",
        name="Tekken 8 (4-Button 3D Fighter)",
        category="fighting",
        description="4-button layout for Tekken 8. Left/Right punch (1,2) on J/I, Left/Right kick (3,4) on K/O, Heat Burst on U, Rage Art on L.",
        socd_mode="neutral",
        deadzone=0.15,
        keymap={
            "KeyW": "DPAD_UP",
            "KeyS": "DPAD_DOWN",
            "KeyA": "DPAD_LEFT",
            "KeyD": "DPAD_RIGHT",
            "KeyJ": "X",          # 1: Left Punch (LP)
            "KeyI": "Y",          # 2: Right Punch (RP)
            "KeyK": "A",          # 3: Left Kick (LK)
            "KeyO": "B",          # 4: Right Kick (RK)
            "KeyU": "RB",         # 2+3 / Heat Burst (R1)
            "KeyL": "RT",         # Rage Art (R2)
            "Space": "LB",        # 1+2 / Special (L1)
            "ShiftLeft": "LT",    # 3+4 / Throw (L2)
            "Enter": "START",
            "Backspace": "BACK",
        },
        labels={
            "X": "1: Left Punch",
            "Y": "2: Right Punch",
            "A": "3: Left Kick",
            "B": "4: Right Kick",
            "RB": "Heat Burst",
            "RT": "Rage Art",
            "LB": "1+2 / Special",
            "LT": "3+4 / Throw",
        }
    ),
    Profile(
        id="platform_fighter",
        name="Platform Fighter (Smash / Rivals)",
        category="platform",
        description="Ergonomic layout for platform fighters. J for Attack, K for Special, Space for Jump, Shift for Shield, U for Grab.",
        socd_mode="neutral",
        deadzone=0.12,
        keymap={
            "KeyW": "DPAD_UP",
            "KeyS": "DPAD_DOWN",
            "KeyA": "DPAD_LEFT",
            "KeyD": "DPAD_RIGHT",
            "KeyJ": "A",          # Standard Attack
            "KeyK": "B",          # Special Attack
            "Space": "X",         # Jump
            "KeyI": "Y",          # Jump 2
            "ShiftLeft": "RT",    # Shield / Dodge
            "KeyU": "LB",         # Grab
            "KeyL": "RB",         # Smash Attack / C-Stick
            "Enter": "START",
            "Backspace": "BACK",
        },
        labels={
            "A": "Standard Attack",
            "B": "Special Attack",
            "X": "Jump",
            "RT": "Shield / Dodge",
            "LB": "Grab",
            "RB": "Smash Attack",
        }
    ),
    Profile(
        id="retro_arcade",
        name="Retro Arcade / Emulator (MAME/SNES)",
        category="retro",
        description="Classic retro controller mapping. A/B/X/Y on J/K/U/I, Shoulders on LB/RB, Coin/Start on Backspace/Enter.",
        socd_mode="neutral",
        deadzone=0.18,
        keymap={
            "KeyW": "DPAD_UP",
            "KeyS": "DPAD_DOWN",
            "KeyA": "DPAD_LEFT",
            "KeyD": "DPAD_RIGHT",
            "KeyJ": "A",          # A Button
            "KeyK": "B",          # B Button
            "KeyU": "X",          # X Button
            "KeyI": "Y",          # Y Button
            "KeyQ": "LB",         # L Shoulder
            "KeyE": "RB",         # R Shoulder
            "Enter": "START",     # Start / 1P
            "Backspace": "BACK",  # Select / Coin
        }
    ),
    Profile(
        id="arrow_keys_player2",
        name="Arrow Keys (NumPad 2P Split)",
        category="custom",
        description="Allows Player 2 to sit at the same physical keyboard using Arrow Keys + Numpad numbers (1-6).",
        socd_mode="neutral",
        deadzone=0.15,
        keymap={
            "ArrowUp": "DPAD_UP",
            "ArrowDown": "DPAD_DOWN",
            "ArrowLeft": "DPAD_LEFT",
            "ArrowRight": "DPAD_RIGHT",
            "Numpad1": "X",
            "Numpad2": "Y",
            "Numpad3": "RB",
            "Numpad4": "A",
            "Numpad5": "B",
            "Numpad6": "RT",
            "Numpad0": "LB",
            "NumpadDecimal": "LT",
            "NumpadEnter": "START",
            "NumpadAdd": "BACK",
        }
    ),
    Profile(
        id="it_takes_two",
        name="It Takes Two (Co-Op Action)",
        category="custom",
        description="Optimized layout for It Takes Two Player 2. Space for Jump, E for Dash, Q for Interact, R for Cancel, Z for Ability, C for Rope Grapple, Shift for LT, Ctrl for RT, CapsLock/F for L3 Sprint.",
        socd_mode="neutral",
        deadzone=0.15,
        keymap={
            "KeyW": "DPAD_UP",
            "KeyS": "DPAD_DOWN",
            "KeyA": "DPAD_LEFT",
            "KeyD": "DPAD_RIGHT",
            "ArrowUp": "DPAD_UP",
            "ArrowDown": "DPAD_DOWN",
            "ArrowLeft": "DPAD_LEFT",
            "ArrowRight": "DPAD_RIGHT",
            "Space": "A",          # Jump
            "KeyE": "X",           # Dash / Action
            "KeyQ": "Y",           # Interact / Secondary
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
            "Enter": "START",
            "Escape": "BACK",
            "F1": "GUIDE",
        },
        labels={
            "A": "Jump (Space)",
            "X": "Dash / Action (E)",
            "Y": "Interact (Q)",
            "B": "Cancel (R)",
            "LB": "Ability (Z)",
            "RB": "Rope Grapple (C)",
            "LT": "Ground Pound (Shift)",
            "RT": "Action / Tool (Ctrl)",
            "L3": "Sprint (Caps/F)",
            "R3": "Camera Focus (G)",
            "START": "Pause (Enter)",
            "BACK": "Menu / Back (Esc)",
        }
    )
]

class ProfileManager:
    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = storage_dir or os.path.join(os.path.dirname(__file__), "..", "profiles")
        os.makedirs(self.storage_dir, exist_ok=True)
        self._profiles: Dict[str, Profile] = {p.id: p for p in BUILTIN_PROFILES}
        self._load_custom_profiles()

    def _load_custom_profiles(self) -> None:
        if not os.path.exists(self.storage_dir):
            return
        for fname in os.listdir(self.storage_dir):
            if fname.endswith(".json"):
                fpath = os.path.join(self.storage_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        p = Profile(**data)
                        self._profiles[p.id] = p
                except Exception:
                    pass

    def get_all(self) -> List[Profile]:
        return list(self._profiles.values())

    def get(self, profile_id: str) -> Optional[Profile]:
        return self._profiles.get(profile_id)

    def save_custom_profile(self, profile: Profile) -> None:
        self._profiles[profile.id] = profile
        fpath = os.path.join(self.storage_dir, f"{profile.id}.json")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(profile.model_dump_json(indent=2))
