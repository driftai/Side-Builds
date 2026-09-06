"""Core OmniPad device, safety, profile, and runtime smoke-test facade."""

import asyncio
import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from router import _refresh_vhf_status, build_keyboard_report
from router.controller import DualShock4Backend, VIGEM_AVAILABLE, Xbox360Backend
from router.profiles import ProfileManager
from router.slot_manager import SlotManager
from router.socd import SOCDCleaner, SOCDMode
from router.tunnel import TunnelManager, get_local_ips
from tests.smoke_runtime_flows import (
    test_canonical_end_to_end_user_journey,
    test_local_background_routing_and_key_streaming,
    test_unfocused_target_routing_behavior,
)
from tools.enumerate_raw_input_keyboards import enumerate_keyboards


def test_section(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  TEST: {title}")
    print("=" * 60)


def test_socd_cleaner() -> None:
    test_section("SOCD Cleaner Algorithms")

    cleaner_neutral = SOCDCleaner(SOCDMode.NEUTRAL)
    result = cleaner_neutral.clean_buttons(
        {"DPAD_LEFT": True, "DPAD_RIGHT": True, "DPAD_UP": False, "DPAD_DOWN": False}
    )
    assert not result["DPAD_LEFT"] and not result["DPAD_RIGHT"]
    print("  [PASS] Neutral Mode: Left + Right = Neutral (0)")

    result = cleaner_neutral.clean_buttons(
        {"DPAD_LEFT": False, "DPAD_RIGHT": False, "DPAD_UP": True, "DPAD_DOWN": True}
    )
    assert not result["DPAD_UP"] and not result["DPAD_DOWN"]
    print("  [PASS] Neutral Mode: Down + Up = Neutral (0)")

    cleaner_up = SOCDCleaner(SOCDMode.UP_PRIORITY)
    result = cleaner_up.clean_buttons({"DPAD_UP": True, "DPAD_DOWN": True})
    assert result["DPAD_UP"] and not result["DPAD_DOWN"]
    print("  [PASS] Up Priority Mode: Down + Up = UP")

    normalized_x, normalized_y = cleaner_neutral.clean_stick(0.08, 0.05, deadzone=0.15)
    assert normalized_x == 0.0 and normalized_y == 0.0
    print("  [PASS] Analog Deadzone Filtering: Sub-threshold noise ignored (0, 0)")


def test_vigem_xbox360() -> None:
    test_section("Native Virtual Xbox 360 Controller (ViGEmBus)")
    if not VIGEM_AVAILABLE:
        print("  [SKIP] ViGEmBus / vgamepad driver not available on this environment.")
        return

    pad = Xbox360Backend(slot_id=1)
    pad.apply({
        "buttons": {"A": True, "X": True, "START": True, "DPAD_UP": True},
        "axes": {"lx": 0.75, "ly": -0.5, "lt": 1.0, "rt": 0.5},
    })
    print("  [PASS] Successfully applied buttons (A, X, Start, Up) and analog sticks to Xbox 360")
    pad.release_all()
    print("  [PASS] Successfully executed release_all() on Xbox 360")
    pad.close()
    print("  [PASS] Cleanly closed virtual Xbox 360 controller")


def test_vigem_ds4() -> None:
    test_section("Native Virtual DualShock 4 Controller (ViGEmBus)")
    if not VIGEM_AVAILABLE:
        print("  [SKIP] ViGEmBus / vgamepad driver not available on this environment.")
        return

    pad = DualShock4Backend(slot_id=1)
    pad.apply({
        "buttons": {"A": True, "B": True, "LB": True, "DPAD_LEFT": True},
        "axes": {"lx": -0.8, "ly": 0.8, "lt": 0.9, "rt": 0.0},
    })
    print("  [PASS] Successfully applied buttons (Cross, Circle, L1, Left) and sticks to DS4")
    pad.release_all()
    print("  [PASS] Successfully executed release_all() on DS4")
    pad.close()
    print("  [PASS] Cleanly closed virtual DualShock 4 controller")


async def test_watchdog_timeout() -> None:
    test_section("Input Watchdog & Stuck Key Auto-Release")
    manager = SlotManager(max_slots=2, watchdog_timeout=0.1)
    await manager.start()

    class DummyWebSocket:
        async def send_json(self, message) -> None:
            del message

    await manager.attach_player(1, "TestGamer", DummyWebSocket())
    await manager.process_input_packet(1, {
        "seq": 1,
        "buttons": {"DPAD_RIGHT": True, "A": True},
        "axes": {"lx": 1.0, "ly": 0.0},
    })
    assert manager.slots[1].is_active is True
    assert manager.slots[1].last_state["buttons"].get("DPAD_RIGHT") is True
    print("  [PASS] Held state registered (is_active = True)")

    await asyncio.sleep(0.18)
    assert manager.slots[1].is_active is False
    assert not manager.slots[1].last_state["buttons"].get("DPAD_RIGHT")
    print("  [PASS] Watchdog auto-neutralized stuck inputs after timeout window")
    await manager.stop()


def test_network_and_tunnel() -> None:
    test_section("Network Discovery & Cloudflare Quick Tunnel")
    local_ips = get_local_ips()
    print(f"  [PASS] Local Network IPs detected: {local_ips}")

    tunnel = TunnelManager(local_port=8000)
    print(f"  [PASS] cloudflared available: {tunnel.is_available()} (Path: {tunnel.cloudflared_path})")


def test_profiles() -> None:
    test_section("Fighting Game & Emulator Profiles")
    profiles = ProfileManager().get_all()
    print(f"  [PASS] Loaded {len(profiles)} profiles:")
    for profile in profiles:
        print(f"         - {profile.name} [{profile.category}] ({len(profile.keymap)} bindings)")


def test_vhf_and_raw_input() -> None:
    test_section("VHF Virtual Keyboard & Raw Input Diagnostics")
    vhf_available, vhf_error = _refresh_vhf_status()
    if vhf_available:
        print("  [PASS] OmniPad VHF KMDF driver is active and ready.")
    else:
        print(f"  [INFO] OmniPad VHF driver not loaded: {vhf_error}")
        print("         Target-Locked SendInput compatibility mode active as fallback.")

    report = build_keyboard_report(["ShiftLeft", "KeyA", "KeyD"])
    assert report[0] == 0x02
    assert report[2] == 0x04
    assert report[3] == 0x07
    print("  [PASS] 8-byte HID report packing verified")

    keyboards = enumerate_keyboards()
    print(f"  [PASS] Raw Input enumerated {len(keyboards)} keyboard device(s)")


async def main_async() -> None:
    test_socd_cleaner()
    test_vigem_xbox360()
    test_vigem_ds4()
    await test_watchdog_timeout()
    test_network_and_tunnel()
    test_profiles()
    test_vhf_and_raw_input()
    await test_unfocused_target_routing_behavior()
    await test_local_background_routing_and_key_streaming()
    await test_canonical_end_to_end_user_journey()

    print("\n" + "=" * 60)
    print("  >>> ALL SMOKE TESTS COMPLETED SUCCESSFULLY! <<<")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main_async())
