"""
Comprehensive Touchscreen Virtual Controller Regression & E2E Test Suite.
Verifies DOM elements, JS state sharing, analog stick & trigger transport,
digital button routing, and end-to-end WebSocket slot state delivery.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
import uvicorn
import websockets

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.slot_manager import SlotManager
from router.controller import Xbox360Backend


def test_touch_controller_assets_and_dom():
    print("\n--- 1. Testing Touchscreen Assets & DOM Element Integrity ---")
    html_path = ROOT / "static" / "play.html"
    js_path = ROOT / "static" / "js" / "touch_controller.js"
    play_js_path = ROOT / "static" / "js" / "play.js"
    css_path = ROOT / "static" / "css" / "touch_controller.css"
    layout_css_path = ROOT / "static" / "css" / "touch_controller_layouts.css"

    assert html_path.exists(), "play.html missing"
    assert js_path.exists(), "touch_controller.js missing"
    assert play_js_path.exists(), "play.js missing"
    assert css_path.exists(), "touch_controller.css missing"
    assert layout_css_path.exists(), "touch_controller_layouts.css missing"

    html = html_path.read_text(encoding="utf-8")
    js = js_path.read_text(encoding="utf-8")
    play_js = play_js_path.read_text(encoding="utf-8")

    # Verify cache-busting link
    assert "touch_controller.css?v=" in html, "touch_controller.css not referenced with cache-busting"
    assert "touch_controller_layouts.css?v=" in html, "touch layout CSS not referenced with cache-busting"
    assert "touch_controller.js?v=" in html, "touch_controller.js not referenced with cache-busting"

    # Verify all essential touch controller DOM element IDs
    required_elements = [
        "touch-left-stick", "touch-left-stick-knob",
        "touch-right-stick", "touch-right-stick-knob",
        "touch-l3-button", "touch-r3-button",
        "touch-lt", "touch-rt",
        "touch-lb", "touch-rb",
        "touch-a", "touch-b", "touch-x", "touch-y",
        "touch-dpad-up", "touch-dpad-down", "touch-dpad-left", "touch-dpad-right",
        "touch-start-2", "touch-back-2", "touch-guide", "touch-touchpad"
    ]
    for el_id in required_elements:
        assert f'id="{el_id}"' in html, f"Missing element id='{el_id}' in play.html"
    print(f"  [PASS] All {len(required_elements)} virtual controller DOM elements present in play.html")

    # Verify canonical touchState sharing
    assert "window.touchState = touchState;" in play_js, "play.js must export window.touchState"
    assert "window.touchState" in js, "touch_controller.js must reference window.touchState"
    assert "captureState" in play_js, "play.js must have captureState"
    print("  [PASS] Canonical touchState sharing verified between play.js and touch_controller.js")


async def test_touch_slot_manager_e2e():
    print("\n--- 2. Testing SlotManager Touch Packet Processing ---")
    sm = SlotManager()
    await sm.set_controller_type(1, "xbox360")
    slot = sm.slots[1]
    assert isinstance(slot.controller, Xbox360Backend)

    # 1. Test Full Analog + Buttons Touch Frame
    touch_packet = {
        "seq": 1,
        "input_surface": "touch",
        "mapping_profile": "universal",
        "buttons": {
            "A": True, "B": False, "X": True, "Y": False,
            "LB": True, "RB": False, "LT": True, "RT": True,
            "START": True, "BACK": False, "GUIDE": True,
            "L3": True, "R3": False,
            "DPAD_UP": True, "DPAD_DOWN": False, "DPAD_LEFT": False, "DPAD_RIGHT": True
        },
        "axes": {
            "lx": 0.75, "ly": -0.85,
            "rx": -0.50, "ry": 0.60,
            "lt": 0.90, "rt": 1.00
        },
        "key_codes": []
    }

    await sm.process_input_packet(1, touch_packet)
    assert slot.last_state["input_surface"] == "touch"
    assert slot.last_state["buttons"]["A"] is True
    assert slot.last_state["buttons"]["X"] is True
    assert slot.last_state["buttons"]["LB"] is True
    assert slot.last_state["buttons"]["START"] is True
    assert slot.last_state["buttons"]["GUIDE"] is True
    assert slot.last_state["buttons"]["L3"] is True
    assert slot.last_state["buttons"]["DPAD_UP"] is True
    assert slot.last_state["buttons"]["DPAD_RIGHT"] is True
    assert slot.last_state["axes"]["lx"] > 0.6
    assert slot.last_state["axes"]["ly"] < -0.7
    assert slot.last_state["axes"]["rx"] < -0.4
    assert slot.last_state["axes"]["ry"] > 0.5
    assert slot.last_state["axes"]["lt"] == 0.90
    assert slot.last_state["axes"]["rt"] == 1.00
    print("  [PASS] Complex touch packet (sticks, analog triggers, face buttons, dpad, menu) applied to Slot 1")

    # 2. Test Release / Neutral Touch Frame
    release_packet = {
        "seq": 2,
        "input_surface": "touch",
        "mapping_profile": "universal",
        "buttons": {
            "A": False, "X": False, "LB": False, "START": False,
            "GUIDE": False, "L3": False, "DPAD_UP": False, "DPAD_RIGHT": False
        },
        "axes": {
            "lx": 0.0, "ly": 0.0,
            "rx": 0.0, "ry": 0.0,
            "lt": 0.0, "rt": 0.0
        },
        "key_codes": []
    }
    await sm.process_input_packet(1, release_packet)
    assert not any(slot.last_state["buttons"].values()), "All buttons must be false on release"
    assert slot.last_state["axes"]["lx"] == 0.0
    assert slot.last_state["axes"]["ly"] == 0.0
    assert slot.last_state["axes"]["rx"] == 0.0
    assert slot.last_state["axes"]["ry"] == 0.0
    assert slot.last_state["axes"]["lt"] == 0.0
    assert slot.last_state["axes"]["rt"] == 0.0
    print("  [PASS] Release packet zeroed all axes and cleared all buttons on Slot 1")


async def test_touch_websocket_stream_e2e():
    print("\n--- 3. Testing WebSocket Touch Input Stream Delivery ---")
    from server import app, slot_manager

    test_port = 8769
    config = uvicorn.Config(app, host="127.0.0.1", port=test_port, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    for _ in range(50):
        if server.started:
            break
        await asyncio.sleep(0.05)

    ws_url = f"ws://127.0.0.1:{test_port}/ws/player"
    try:
        async with websockets.connect(ws_url) as ws:
            # 1. Join Slot 1
            join_msg = {
                "type": "join",
                "slot_id": 1,
                "name": "TouchMobilePlayer",
                "code": "SF6-ROOM",
                "source": "browser"
            }
            await ws.send(json.dumps(join_msg))
            ack = json.loads(await ws.recv())
            assert ack.get("type") == "joined" and ack.get("slot_id") == 1
            print("  [PASS] WebSocket join acknowledged for TouchMobilePlayer on Slot 1")

            slot = slot_manager.slots[1]

            # 2. Stream Touch Input Frame (Sticks + Triggers + Buttons)
            touch_frame = {
                "type": "input",
                "seq": 10,
                "input_surface": "touch",
                "mapping_profile": "universal",
                "buttons": {
                    "A": True, "B": True, "X": False, "Y": False,
                    "LB": False, "RB": True, "LT": False, "RT": True,
                    "START": True, "BACK": False, "GUIDE": False,
                    "L3": False, "R3": True,
                    "DPAD_UP": False, "DPAD_DOWN": True, "DPAD_LEFT": True, "DPAD_RIGHT": False
                },
                "axes": {
                    "lx": -0.65, "ly": 0.80,
                    "rx": 0.90, "ry": -0.40,
                    "lt": 0.0, "rt": 0.95
                },
                "key_codes": []
            }
            await ws.send(json.dumps(touch_frame))
            await asyncio.sleep(0.05)

            assert slot.last_state["input_surface"] == "touch"
            assert slot.last_state["buttons"]["A"] is True
            assert slot.last_state["buttons"]["B"] is True
            assert slot.last_state["buttons"]["RB"] is True
            assert slot.last_state["buttons"]["START"] is True
            assert slot.last_state["buttons"]["R3"] is True
            assert slot.last_state["buttons"]["DPAD_DOWN"] is True
            assert slot.last_state["axes"]["lx"] < -0.5
            assert slot.last_state["axes"]["ly"] > 0.6
            assert slot.last_state["axes"]["rx"] > 0.7
            assert slot.last_state["axes"]["ry"] < -0.3
            assert slot.last_state["axes"]["rt"] == 0.95
            print("  [PASS] Real-time touch WebSocket frame received, decoded, and routed to virtual controller")

            # 3. Stream Stick Return-to-Center Frame
            center_frame = {
                "type": "input",
                "seq": 11,
                "input_surface": "touch",
                "mapping_profile": "universal",
                "buttons": {},
                "axes": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0},
                "key_codes": []
            }
            await ws.send(json.dumps(center_frame))
            await asyncio.sleep(0.05)

            assert slot.last_state["axes"]["lx"] == 0.0
            assert slot.last_state["axes"]["ly"] == 0.0
            assert slot.last_state["axes"]["rx"] == 0.0
            assert slot.last_state["axes"]["ry"] == 0.0
            assert slot.last_state["axes"]["rt"] == 0.0
            print("  [PASS] Stick return-to-center frame successfully reset analog axes")

    finally:
        server.should_exit = True
        await server_task


async def test_touch_multitouch_and_simultaneous_controls():
    print("\n--- 4. Testing Multi-Touch Simultaneous Input & Pointer Isolation ---")
    sm = SlotManager()
    await sm.set_controller_type(1, "xbox360")
    slot = sm.slots[1]

    # Scenario: Thumb 1 moves LS forward-right, Thumb 2 aims RS left,
    # Finger 3 pulls RT trigger, Finger 4 presses A button
    multi_touch_packet = {
        "seq": 20,
        "input_surface": "touch",
        "mapping_profile": "universal",
        "buttons": {"A": True, "RT": True, "L3": True},
        "axes": {
            "lx": 0.85, "ly": 0.85,
            "rx": -0.75, "ry": 0.00,
            "lt": 0.00, "rt": 0.90
        },
        "key_codes": []
    }
    await sm.process_input_packet(1, multi_touch_packet)
    assert slot.last_state["buttons"]["A"] is True
    assert slot.last_state["buttons"]["L3"] is True
    assert slot.last_state["axes"]["lx"] > 0.6
    assert slot.last_state["axes"]["ly"] > 0.6
    assert slot.last_state["axes"]["rx"] < -0.5
    assert slot.last_state["axes"]["rt"] == 0.90
    print("  [PASS] Simultaneous 4-point multi-touch (LS + RS + A + RT + L3) processed cleanly")

    # Scenario: Release LS pointer (Thumb 1 lifts up) while Thumb 2 (RS), Finger 3 (RT), Finger 4 (A) remain held
    ls_release_packet = {
        "seq": 21,
        "input_surface": "touch",
        "mapping_profile": "universal",
        "buttons": {"A": True, "RT": True, "L3": False},
        "axes": {
            "lx": 0.00, "ly": 0.00,
            "rx": -0.75, "ry": 0.00,
            "lt": 0.00, "rt": 0.90
        },
        "key_codes": []
    }
    await sm.process_input_packet(1, ls_release_packet)
    assert slot.last_state["axes"]["lx"] == 0.0
    assert slot.last_state["axes"]["ly"] == 0.0
    # Independent controls remain completely unaffected
    assert slot.last_state["axes"]["rx"] < -0.5
    assert slot.last_state["axes"]["rt"] == 0.90
    assert slot.last_state["buttons"]["A"] is True
    assert slot.last_state["buttons"]["L3"] is False
    print("  [PASS] Pointer isolation verified: releasing LS pointer did not release or corrupt active RS, RT, or A button")


async def test_touch_dualshock4_backend_routing():
    print("\n--- 5. Testing Touch Controls to DualShock 4 Backend Routing ---")
    from router.controller import DualShock4Backend
    sm = SlotManager()
    await sm.set_controller_type(1, "ds4")
    slot = sm.slots[1]
    assert isinstance(slot.controller, DualShock4Backend)

    ds4_touch_packet = {
        "seq": 30,
        "input_surface": "touch",
        "mapping_profile": "universal",
        "buttons": {
            "A": True, "B": True, "X": True, "Y": True,
            "LB": True, "RB": True, "START": True, "GUIDE": True
        },
        "axes": {
            "lx": -0.70, "ly": 0.70,
            "rx": 0.60, "ry": -0.60,
            "lt": 0.80, "rt": 0.85
        },
        "key_codes": []
    }
    await sm.process_input_packet(1, ds4_touch_packet)
    assert slot.last_state["buttons"]["A"] is True
    assert slot.last_state["buttons"]["B"] is True
    assert slot.last_state["buttons"]["X"] is True
    assert slot.last_state["buttons"]["Y"] is True
    assert slot.last_state["buttons"]["LB"] is True
    assert slot.last_state["buttons"]["RB"] is True
    assert slot.last_state["axes"]["lx"] < -0.5
    assert slot.last_state["axes"]["ly"] > 0.5
    assert slot.last_state["axes"]["lt"] == 0.80
    assert slot.last_state["axes"]["rt"] == 0.85
    print("  [PASS] Touch controls correctly mapped and applied to virtual DualShock 4 controller")


def main():
    print("=" * 70)
    print("  OMNIPAD TOUCHSCREEN CONTROLLER AUTOMATED TEST SUITE")
    print("=" * 70)

    test_touch_controller_assets_and_dom()
    asyncio.run(test_touch_slot_manager_e2e())
    asyncio.run(test_touch_websocket_stream_e2e())
    asyncio.run(test_touch_multitouch_and_simultaneous_controls())
    asyncio.run(test_touch_dualshock4_backend_routing())

    print("\n" + "=" * 70)
    print("  >>> ALL TOUCHSCREEN CONTROLLER TESTS PASSED SUCCESSFULLY! <<<")
    print("=" * 70)


if __name__ == "__main__":
    main()
