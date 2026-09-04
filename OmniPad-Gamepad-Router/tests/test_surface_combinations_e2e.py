import asyncio
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.slot_manager import SlotManager
from router.controller import Xbox360Backend, DualShock4Backend, TargetLockedKeyboardBackend, KeyboardInjectionBackend


async def run_surface_combinations_e2e():
    print("\n" + "=" * 70)
    print("  TEST: End-to-End Surface <-> Output Routing Combinations")
    print("=" * 70)

    sm = SlotManager()

    # -------------------------------------------------------------
    # Combination A: Remote Keyboard surface -> Xbox 360 Output
    # -------------------------------------------------------------
    await sm.set_controller_type(1, "xbox360")
    slot1 = sm.slots[1]
    assert isinstance(slot1.controller, Xbox360Backend)

    kb_to_xbox_packet = {
        "seq": 1,
        "input_surface": "keyboard",
        "mapping_profile": "universal",
        "buttons": {
            "A": True,
            "B": True,
            "LB": True,
            "LT": True,
            "START": True,
            "BACK": True,
        },
        "axes": {"lx": -1.0, "ly": 1.0, "rx": 0.0, "ry": 0.0, "lt": 1.0, "rt": 0.0},
        "key_codes": ["KeyW", "KeyA", "KeyU", "KeyI", "Space", "ShiftLeft", "Enter", "KeyZ", "Escape"],
    }
    await sm.process_input_packet(1, kb_to_xbox_packet)
    assert slot1.last_state["input_surface"] == "keyboard"
    assert slot1.last_state["axes"]["ly"] == 1.0
    assert slot1.last_state["axes"]["lx"] == -1.0
    assert slot1.last_state["axes"]["lt"] == 1.0
    assert slot1.last_state["buttons"]["A"] is True
    assert slot1.last_state["buttons"]["B"] is True
    assert slot1.last_state["buttons"]["LB"] is True
    assert slot1.last_state["buttons"]["LT"] is True
    assert slot1.last_state["buttons"]["START"] is True
    assert slot1.last_state["buttons"]["BACK"] is True
    assert "KeyW" in slot1.last_state["key_codes"]
    print("  [PASS] Combination A: Remote Keyboard Surface -> Xbox 360 Output (Resolved browser axes/buttons applied, raw keys preserved)")

    # -------------------------------------------------------------
    # Combination B: Remote Keyboard surface -> Keyboard Output
    # -------------------------------------------------------------
    await sm.set_controller_type(1, "keyboard")
    assert isinstance(slot1.controller, KeyboardInjectionBackend)

    kb_to_kb_packet = {
        "seq": 2,
        "input_surface": "keyboard",
        "buttons": {},
        "axes": {},
        "key_codes": ["KeyW", "KeyU", "KeyI", "KeyM", "Space"],
    }
    await sm.process_input_packet(1, kb_to_kb_packet)
    # W=0x57, U=0x55, I=0x49, M=0x4D, Space=0x20
    assert slot1.controller._down_keys == {0x57, 0x55, 0x49, 0x4D, 0x20}
    slot1.controller.release_all()
    print("  [PASS] Combination B: Remote Keyboard Surface -> Keyboard Output (Raw key identity preserved)")

    # -------------------------------------------------------------
    # Combination C: Remote Gamepad surface -> Keyboard Output
    # -------------------------------------------------------------
    gp_to_kb_packet = {
        "seq": 3,
        "input_surface": "gamepad",
        "buttons": {"A": True, "B": True, "DPAD_UP": True},
        "axes": {},
        "key_codes": [],
    }
    await sm.process_input_packet(1, gp_to_kb_packet)
    # TargetLocked / Legacy keymap: DPAD_UP=0x57(W), A=0x4A(J), B=0x4B(K)
    assert 0x57 in slot1.controller._down_keys  # W
    assert 0x4A in slot1.controller._down_keys  # J
    assert 0x4B in slot1.controller._down_keys  # K
    slot1.controller.release_all()
    print("  [PASS] Combination C: Remote Gamepad Surface -> Keyboard Output (Normalized buttons mapped)")

    # -------------------------------------------------------------
    # Combination D: Remote Touch surface -> DualShock 4 Output
    # -------------------------------------------------------------
    await sm.set_controller_type(1, "ds4")
    assert isinstance(slot1.controller, DualShock4Backend)

    touch_to_ds4_packet = {
        "seq": 4,
        "input_surface": "touch",
        "buttons": {"X": True, "Y": True, "DPAD_DOWN": True, "START": True},
        "axes": {"lx": 0, "ly": 0, "rx": 0, "ry": 0, "lt": 0, "rt": 0},
        "key_codes": [],
    }
    await sm.process_input_packet(1, touch_to_ds4_packet)
    assert slot1.last_state["buttons"]["X"] is True
    assert slot1.last_state["buttons"]["Y"] is True
    assert slot1.last_state["buttons"]["DPAD_DOWN"] is True
    assert slot1.last_state["buttons"]["START"] is True
    print("  [PASS] Combination D: Remote Touch Surface -> DualShock 4 Output")

    await sm.stop()
    print("  >>> ALL 4 SURFACE <-> OUTPUT COMBINATIONS VALIDATED SUCCESSFULLY! <<<\n")


if __name__ == "__main__":
    asyncio.run(run_surface_combinations_e2e())
