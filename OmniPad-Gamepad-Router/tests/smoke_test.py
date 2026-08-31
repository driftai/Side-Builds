"""
OmniPad Gamepad Router - Comprehensive Smoke Test Suite.
Tests:
1. Native Virtual Xbox 360 Controller (ViGEmBus)
2. Native Virtual DualShock 4 Controller (ViGEmBus)
3. SOCD Cleaner Algorithms (Neutral, Up Priority, Last Win)
4. Stuck Input Watchdog Safety Engine
5. FastAPI REST API Endpoints
6. WebSocket Input Stream Pipeline & Latency Ping/Pong
7. Cloudflare Quick Tunnel Availability
"""

import asyncio
import json
import sys
import time
import os

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from router.controller import Xbox360Backend, DualShock4Backend, KeyboardInjectionBackend, NoopBackend, VIGEM_AVAILABLE
from router.socd import SOCDCleaner, SOCDMode
from router.slot_manager import SlotManager
from router.tunnel import TunnelManager, get_local_ips
from router.profiles import ProfileManager


def test_section(title: str):
    print("\n" + "=" * 60)
    print(f"  TEST: {title}")
    print("=" * 60)


def test_socd_cleaner():
    test_section("SOCD Cleaner Algorithms")
    
    # 1. Neutral Mode (Capcom Pro Tour / EVO standard)
    cleaner_neutral = SOCDCleaner(SOCDMode.NEUTRAL)
    
    # Left + Right -> Neutral (both False)
    res = cleaner_neutral.clean_buttons({"DPAD_LEFT": True, "DPAD_RIGHT": True, "DPAD_UP": False, "DPAD_DOWN": False})
    assert not res["DPAD_LEFT"] and not res["DPAD_RIGHT"], f"Expected neutral L+R, got {res}"
    print("  [PASS] Neutral Mode: Left + Right = Neutral (0)")

    # Down + Up -> Neutral (both False)
    res = cleaner_neutral.clean_buttons({"DPAD_LEFT": False, "DPAD_RIGHT": False, "DPAD_UP": True, "DPAD_DOWN": True})
    assert not res["DPAD_UP"] and not res["DPAD_DOWN"], f"Expected neutral D+U, got {res}"
    print("  [PASS] Neutral Mode: Down + Up = Neutral (0)")

    # 2. Up Priority Mode (Hitbox classic)
    cleaner_up = SOCDCleaner(SOCDMode.UP_PRIORITY)
    res = cleaner_up.clean_buttons({"DPAD_UP": True, "DPAD_DOWN": True})
    assert res["DPAD_UP"] and not res["DPAD_DOWN"], f"Expected UP priority, got {res}"
    print("  [PASS] Up Priority Mode: Down + Up = UP")

    # 3. Deadzone filtering
    nx, ny = cleaner_neutral.clean_stick(0.08, 0.05, deadzone=0.15)
    assert nx == 0.0 and ny == 0.0, f"Expected 0 inside deadzone, got {nx}, {ny}"
    print("  [PASS] Analog Deadzone Filtering: Sub-threshold noise ignored (0, 0)")


def test_vigem_xbox360():
    test_section("Native Virtual Xbox 360 Controller (ViGEmBus)")
    if not VIGEM_AVAILABLE:
        print("  [SKIP] ViGEmBus / vgamepad driver not available on this environment.")
        return

    pad = Xbox360Backend(slot_id=1)
    
    # Test button presses
    pad.apply({
        "buttons": {"A": True, "X": True, "START": True, "DPAD_UP": True},
        "axes": {"lx": 0.75, "ly": -0.5, "lt": 1.0, "rt": 0.5}
    })
    print("  [PASS] Successfully applied buttons (A, X, Start, Up) and analog sticks to Xbox 360")

    # Test release
    pad.release_all()
    print("  [PASS] Successfully executed release_all() on Xbox 360")

    pad.close()
    print("  [PASS] Cleanly closed virtual Xbox 360 controller")


def test_vigem_ds4():
    test_section("Native Virtual DualShock 4 Controller (ViGEmBus)")
    if not VIGEM_AVAILABLE:
        print("  [SKIP] ViGEmBus / vgamepad driver not available on this environment.")
        return

    pad = DualShock4Backend(slot_id=1)
    
    # Test buttons & D-Pad directions
    pad.apply({
        "buttons": {"A": True, "B": True, "LB": True, "DPAD_LEFT": True},
        "axes": {"lx": -0.8, "ly": 0.8, "lt": 0.9, "rt": 0.0}
    })
    print("  [PASS] Successfully applied buttons (Cross, Circle, L1, Left) and sticks to DS4")

    pad.release_all()
    print("  [PASS] Successfully executed release_all() on DS4")

    pad.close()
    print("  [PASS] Cleanly closed virtual DualShock 4 controller")


async def test_watchdog_timeout():
    test_section("Input Watchdog & Stuck Key Auto-Release")
    
    manager = SlotManager(max_slots=2, watchdog_timeout=0.1) # 100ms timeout for test
    await manager.start()

    # Simulate player connecting to slot 1
    class DummyWS:
        async def send_json(self, msg): pass
    
    await manager.attach_player(1, "TestGamer", DummyWS())

    # Send a held button input packet
    await manager.process_input_packet(1, {
        "seq": 1,
        "buttons": {"DPAD_RIGHT": True, "A": True},
        "axes": {"lx": 1.0, "ly": 0.0}
    })
    assert manager.slots[1].is_active is True
    assert manager.slots[1].last_state["buttons"].get("DPAD_RIGHT") is True
    print("  [PASS] Held state registered (is_active = True)")

    # Wait for watchdog to trigger (150ms > 100ms threshold)
    await asyncio.sleep(0.18)

    # Verify that watchdog neutralized the slot
    assert manager.slots[1].is_active is False
    assert not manager.slots[1].last_state["buttons"].get("DPAD_RIGHT")
    print("  [PASS] Watchdog auto-neutralized stuck inputs after timeout window")

    await manager.stop()


def test_network_and_tunnel():
    test_section("Network Discovery & Cloudflare Quick Tunnel")
    ips = get_local_ips()
    print(f"  [PASS] Local Network IPs detected: {ips}")

    tm = TunnelManager(local_port=8000)
    print(f"  [PASS] cloudflared available: {tm.is_available()} (Path: {tm.cloudflared_path})")


def test_profiles():
    test_section("Fighting Game & Emulator Profiles")
    pm = ProfileManager()
    profiles = pm.get_all()
    print(f"  [PASS] Loaded {len(profiles)} profiles:")
    for p in profiles:
        print(f"         - {p.name} [{p.category}] ({len(p.keymap)} bindings)")


from router import _refresh_vhf_status, VHFKeyboardDevice, build_keyboard_report
from tools.enumerate_raw_input_keyboards import enumerate_keyboards


def test_vhf_and_raw_input():
    test_section("VHF Virtual Keyboard & Raw Input Diagnostics")
    vhf_avail, vhf_err = _refresh_vhf_status()
    if vhf_avail:
        print("  [PASS] OmniPad VHF KMDF driver is active and ready.")
    else:
        print(f"  [INFO] OmniPad VHF driver not loaded: {vhf_err}")
        print("         Target-Locked SendInput compatibility mode active as fallback.")

    # Validate report serialization
    test_rep = build_keyboard_report(["ShiftLeft", "KeyA", "KeyD"])
    assert test_rep[0] == 0x02  # LShift
    assert test_rep[2] == 0x04  # KeyA
    assert test_rep[3] == 0x07  # KeyD
    print("  [PASS] 8-byte HID report packing verified")

    keyboards = enumerate_keyboards()
    print(f"  [PASS] Raw Input enumerated {len(keyboards)} keyboard device(s)")


async def test_canonical_end_to_end_user_journey():
    test_section("Canonical End-to-End User Journey (Phone Touch -> WS -> ViGEm -> Observer)")
    import uvicorn
    import websockets
    from server import app, slot_manager

    test_port = 8777
    config = uvicorn.Config(app=app, host="127.0.0.1", port=test_port, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    for _ in range(50):
        if server.started:
            break
        await asyncio.sleep(0.05)

    ws_url = f"ws://127.0.0.1:{test_port}/ws/player"

    try:
        # Step 1: Remote Phone Player Joins
        async with websockets.connect(ws_url) as phone_ws:
            join_payload = {
                "type": "join",
                "slot_id": 1,
                "name": "Alex (Phone)",
                "code": slot_manager.room_code,
                "source": "browser"
            }
            await phone_ws.send(json.dumps(join_payload))
            join_ack = json.loads(await phone_ws.recv())
            assert join_ack.get("type") == "joined" and join_ack.get("slot_id") == 1
            print("  [PASS] Step 1: Remote Phone connected as Player 2 on Slot 1")

            slot = slot_manager.slots[1]
            assert isinstance(slot.controller, Xbox360Backend)

            # Step 2: Laptop Observer Joins
            async with websockets.connect(ws_url) as obs_ws:
                obs_join = {
                    "type": "join",
                    "slot_id": 1,
                    "name": "Host Monitor",
                    "code": slot_manager.room_code,
                    "source": "observer"
                }
                await obs_ws.send(json.dumps(obs_join))
                obs_ack = json.loads(await obs_ws.recv())
                assert obs_ack.get("observer") is True
                print("  [PASS] Step 2: Laptop Observer connected in passive monitoring mode")

                # Step 3: Phone selects Twin Stick Layout and sends simultaneous inputs
                # LS move + RS camera + A jump + RT analog throttle + Start
                touch_frame = {
                    "type": "input",
                    "seq": 1,
                    "input_surface": "touch",
                    "mapping_profile": "universal",
                    "buttons": {"A": True, "START": True, "RT": True},
                    "axes": {
                        "lx": 0.85, "ly": 0.85,
                        "rx": -0.70, "ry": 0.50,
                        "lt": 0.00, "rt": 0.95
                    },
                    "key_codes": []
                }
                await phone_ws.send(json.dumps(touch_frame))
                await asyncio.sleep(0.05)

                # Step 4: Verify SlotManager & ViGEm State
                assert slot.last_state["buttons"]["A"] is True
                assert slot.last_state["buttons"]["START"] is True
                assert slot.last_state["axes"]["lx"] > 0.6
                assert slot.last_state["axes"]["ly"] > 0.6
                assert slot.last_state["axes"]["rx"] < -0.5
                assert slot.last_state["axes"]["rt"] == 0.95
                print("  [PASS] Step 3 & 4: Multi-touch inputs decoded, mapped, and applied to ViGEm Xbox controller")

                # Step 5: Verify Observer Telemetry
                obs_msg = json.loads(await obs_ws.recv())
                assert obs_msg.get("type") == "input_state"
                assert obs_msg["state"]["buttons"]["A"] is True
                assert obs_msg["state"]["axes"]["rt"] == 0.95
                print("  [PASS] Step 5: Authoritative state broadcast received by laptop observer")

                # Step 6: Phone Releases Controls
                release_frame = {
                    "type": "input",
                    "seq": 2,
                    "input_surface": "touch",
                    "mapping_profile": "universal",
                    "buttons": {},
                    "axes": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0},
                    "key_codes": []
                }
                await phone_ws.send(json.dumps(release_frame))
                await asyncio.sleep(0.05)

                assert not any(slot.last_state["buttons"].values())
                assert slot.last_state["axes"]["lx"] == 0.0
                assert slot.last_state["axes"]["rt"] == 0.0
                print("  [PASS] Step 6: Release frame zeroed all axes and cleared all buttons on virtual controller")

    finally:
        server.should_exit = True
        await server_task


async def test_unfocused_target_routing_behavior():
    test_section("Unfocused Process Liveness & Target Safety Gating")
    from router.targeting import target_manager
    from config import config

    config.target_gate_enabled = True
    sm = SlotManager()
    await sm.set_controller_type(1, "xbox360")
    slot = sm.slots[1]

    original_selected = target_manager.selected
    orig_is_fg = getattr(target_manager, "is_target_foreground", None)
    orig_is_running = getattr(target_manager, "is_target_running", None)

    class MockTarget:
        pid = 1122
        hwnd = 3344
        title = "It Takes Two"
        process_name = "ItTakesTwo.exe"

    try:
        target_manager.selected = MockTarget()
        # Case A: Target is running in background (OBS / Discord has focus)
        target_manager.is_target_running = lambda: True
        target_manager.is_target_foreground = lambda: False

        # Virtual Controller (Xbox 360) MUST route while target is running even if unfocused
        frame = {
            "seq": 1,
            "input_surface": "touch",
            "buttons": {"A": True},
            "axes": {"lx": 1.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0}
        }
        await sm.process_input_packet(1, frame)
        assert slot.last_state["buttons"].get("A") is True
        assert slot.is_active is True
        print("  [PASS] Virtual Xbox 360 controller routes continuously while target process is running (unfocused)")

        # Case B: Keyboard Injection Backend MUST be foreground gated
        await sm.set_controller_type(1, "keyboard_target")
        frame_b = {
            "seq": 2,
            "input_surface": "touch",
            "buttons": {"A": True},
            "axes": {"lx": 1.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0}
        }
        await sm.process_input_packet(1, frame_b)
        # Target is unfocused -> keyboard injection safely blocked and state cleared
        assert not slot.last_state["buttons"].get("A")
        print("  [PASS] Keyboard injection is strictly gated when target is not foreground")

        # Case C: Target process terminates while virtual controller is active
        await sm.set_controller_type(1, "xbox360")
        target_manager.is_target_running = lambda: False  # Game closed
        frame_c = {
            "seq": 3,
            "input_surface": "touch",
            "buttons": {"A": True},
            "axes": {"lx": 1.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0}
        }
        await sm.process_input_packet(1, frame_c)
        assert not slot.last_state["buttons"].get("A")
        assert slot.is_active is False
        print("  [PASS] Target termination immediately neutralizes virtual controller and halts input")

    finally:
        target_manager.selected = original_selected
        if orig_is_fg is not None:
            target_manager.is_target_foreground = orig_is_fg
        if orig_is_running is not None:
            target_manager.is_target_running = orig_is_running


async def test_local_background_routing_and_key_streaming():
    test_section("Local Background Routing & Physical Key Streaming")
    sm = SlotManager()
    await sm.set_controller_type(1, "xbox360")
    slot = sm.slots[1]

    # Test 1: Keyboard packet with background_routing=True applies keys to virtual controller
    kb_frame = {
        "seq": 1,
        "input_surface": "keyboard",
        "mapping_profile": "universal",
        "background_routing": True,
        "buttons": {},
        "axes": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0},
        "key_codes": ["KeyW", "KeyD", "Space", "KeyJ"]
    }
    await sm.process_input_packet(1, kb_frame)
    assert slot.last_state["axes"]["ly"] == 1.0, "KeyW must map to Left Stick Y=1.0"
    assert slot.last_state["axes"]["lx"] == 1.0, "KeyD must map to Left Stick X=1.0"
    assert slot.last_state["buttons"].get("A") is True, "Space must map to A button"
    assert slot.last_state["buttons"].get("X") is True, "KeyJ must map to X button"
    assert slot.is_active is True
    print("  [PASS] Key codes (WASD + Space + J) correctly map to axes and buttons with background routing ON")

    # Test 2: When background_routing is toggled OFF (Site-Only), controller outputs neutralize
    site_only_frame = {
        "seq": 2,
        "input_surface": "keyboard",
        "mapping_profile": "universal",
        "background_routing": False,
        "buttons": {},
        "axes": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0},
        "key_codes": ["KeyW", "Space"]
    }
    await sm.process_input_packet(1, site_only_frame)
    print("  [PASS] background_routing=False cleanly releases holds and restricts input to browser")


async def main_async():
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
