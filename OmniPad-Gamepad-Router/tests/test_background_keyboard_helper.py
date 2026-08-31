"""
OmniPad Background Keyboard Helper & WebSocket Handoff Test Suite.
Verifies pynput-to-DOM key conversion, SOCD neutrality, action mappings,
hotkey toggle safety, and multi-connection WebSocket handoff resilience.
"""
import asyncio
import json
import pathlib
import sys
import uvicorn
import websockets
from pynput import keyboard

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import app, slot_manager
from static.tools.background_keyboard_helper import (
    key_to_code,
    websocket_url_from_play_url,
    build_packet,
    ALLOWED_CODES,
    BackgroundKeyboardClient
)


def test_key_mappings_and_punctuation():
    print("\n" + "=" * 70)
    print("  TEST 1: Key-to-Code & Punctuation Translation")
    print("=" * 70)

    # 1. Letters & Digits
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        k = keyboard.KeyCode.from_char(ch.lower())
        code = key_to_code(k)
        assert code == f"Key{ch}", f"Expected Key{ch}, got {code}"
        assert code in ALLOWED_CODES

    for digit in "0123456789":
        k = keyboard.KeyCode.from_char(digit)
        code = key_to_code(k)
        assert code == f"Digit{digit}", f"Expected Digit{digit}, got {code}"
        assert code in ALLOWED_CODES

    # 2. Punctuation
    puncts = {
        "`": "Backquote", "-": "Minus", "=": "Equal",
        "[": "BracketLeft", "]": "BracketRight", "\\": "Backslash",
        ";": "Semicolon", "'": "Quote", ",": "Comma", ".": "Period", "/": "Slash"
    }
    for char, expected_code in puncts.items():
        k = keyboard.KeyCode.from_char(char)
        code = key_to_code(k)
        assert code == expected_code, f"Expected {expected_code} for char '{char}', got {code}"
        assert code in ALLOWED_CODES, f"{code} not in ALLOWED_CODES"

    # 3. Special & Navigation Keys
    assert key_to_code(keyboard.Key.space) == "Space"
    assert key_to_code(keyboard.Key.enter) == "Enter"
    assert key_to_code(keyboard.Key.esc) == "Escape"
    assert key_to_code(keyboard.Key.tab) == "Tab"
    assert key_to_code(keyboard.Key.backspace) == "Backspace"
    assert key_to_code(keyboard.Key.shift_l) == "ShiftLeft"
    assert key_to_code(keyboard.Key.shift_r) == "ShiftRight"
    assert key_to_code(keyboard.Key.ctrl_l) == "ControlLeft"
    assert key_to_code(keyboard.Key.ctrl_r) == "ControlRight"
    assert key_to_code(keyboard.Key.alt_l) == "AltLeft"
    assert key_to_code(keyboard.Key.alt_r) == "AltRight"
    assert key_to_code(keyboard.Key.up) == "ArrowUp"
    assert key_to_code(keyboard.Key.down) == "ArrowDown"
    assert key_to_code(keyboard.Key.left) == "ArrowLeft"
    assert key_to_code(keyboard.Key.right) == "ArrowRight"
    assert key_to_code(keyboard.Key.f1) == "F1"
    assert key_to_code(keyboard.Key.f12) == "F12"

    print("  [PASS] All character, digit, punctuation, and navigation keys mapped correctly.")


def test_packet_generation_and_socd():
    print("\n" + "=" * 70)
    print("  TEST 2: Analog Motion, SOCD Neutral, and Action Button Mapping")
    print("=" * 70)

    # 1. Left Stick (WASD)
    pkt_w = build_packet({"KeyW"}, 1)
    assert pkt_w["axes"]["ly"] == 1.0 and pkt_w["axes"]["lx"] == 0.0

    pkt_s = build_packet({"KeyS"}, 2)
    assert pkt_s["axes"]["ly"] == -1.0 and pkt_s["axes"]["lx"] == 0.0

    pkt_ws = build_packet({"KeyW", "KeyS"}, 3)
    assert pkt_ws["axes"]["ly"] == 0.0, "Opposing W+S must be SOCD neutral"

    pkt_ad = build_packet({"KeyA", "KeyD"}, 4)
    assert pkt_ad["axes"]["lx"] == 0.0, "Opposing A+D must be SOCD neutral"

    pkt_diag = build_packet({"KeyW", "KeyD"}, 5)
    assert pkt_diag["axes"]["ly"] == 1.0 and pkt_diag["axes"]["lx"] == 1.0

    # 2. Right Stick (Arrow Keys)
    pkt_up = build_packet({"ArrowUp"}, 6)
    assert pkt_up["axes"]["ry"] == 1.0 and pkt_up["axes"]["rx"] == 0.0

    pkt_ud = build_packet({"ArrowUp", "ArrowDown"}, 7)
    assert pkt_ud["axes"]["ry"] == 0.0, "Opposing Arrow Up+Down must be SOCD neutral"

    pkt_lr = build_packet({"ArrowLeft", "ArrowRight"}, 8)
    assert pkt_lr["axes"]["rx"] == 0.0, "Opposing Arrow Left+Right must be SOCD neutral"

    # 3. Action Buttons & Triggers
    pkt_actions = build_packet({
        "Space", "KeyE", "KeyQ", "KeyR",
        "ShiftLeft", "ControlLeft", "KeyZ", "KeyC",
        "Enter", "Escape", "F1",
        "Digit1", "Digit2", "Digit3", "Digit4"
    }, 9)

    assert pkt_actions["buttons"]["A"] is True
    assert pkt_actions["buttons"]["X"] is True
    assert pkt_actions["buttons"]["Y"] is True
    assert pkt_actions["buttons"]["B"] is True
    assert pkt_actions["buttons"]["LB"] is True
    assert pkt_actions["buttons"]["RB"] is True
    assert pkt_actions["buttons"]["START"] is True
    assert pkt_actions["buttons"]["BACK"] is True
    assert pkt_actions["buttons"]["GUIDE"] is True
    assert pkt_actions["buttons"]["DPAD_UP"] is True
    assert pkt_actions["buttons"]["DPAD_DOWN"] is True
    assert pkt_actions["buttons"]["DPAD_LEFT"] is True
    assert pkt_actions["buttons"]["DPAD_RIGHT"] is True
    assert pkt_actions["axes"]["lt"] == 1.0
    assert pkt_actions["axes"]["rt"] == 1.0

    print("  [PASS] SOCD neutral cancellation and action mappings verified.")


def test_url_parser():
    print("\n" + "=" * 70)
    print("  TEST 3: WebSocket URL Parser from Play Link")
    print("=" * 70)

    url1 = "http://192.168.1.209:8000/play?code=SF6-ROOM"
    ws1, code1 = websocket_url_from_play_url(url1)
    assert ws1 == "ws://192.168.1.209:8000/ws/player"
    assert code1 == "SF6-ROOM"

    url2 = "https://omnipad-remote.trycloudflare.com/play?code=COOP-44"
    ws2, code2 = websocket_url_from_play_url(url2)
    assert ws2 == "wss://omnipad-remote.trycloudflare.com/ws/player"
    assert code2 == "COOP-44"

    print("  [PASS] URL parsing handles LAN HTTP and Cloudflare HTTPS/WSS correctly.")


def test_pause_hotkey_logic():
    print("\n" + "=" * 70)
    print("  TEST 4: Hotkey Pause & Safe Input Neutralization")
    print("=" * 70)

    client = BackgroundKeyboardClient("ws://127.0.0.1:8000/ws/player", "TEST", 1, "Player 2")
    assert client.capture_enabled is True

    # Simulate pressing W and Space
    client.on_press(keyboard.KeyCode.from_char("w"))
    client.on_press(keyboard.Key.space)
    assert "KeyW" in client.active
    assert "Space" in client.active

    # Simulate pressing Ctrl + Alt + F8
    client.on_press(keyboard.Key.ctrl_l)
    client.on_press(keyboard.Key.alt_l)
    client.on_press(keyboard.Key.f8)

    assert client.capture_enabled is False, "Ctrl+Alt+F8 should have paused capture"
    assert len(client.active) == 0, "Pausing capture must clear all active inputs to prevent stuck keys"

    # Simulate releasing keys and pressing Ctrl + Alt + F8 again to resume
    client.on_release(keyboard.Key.f8)
    client.on_press(keyboard.Key.f8)
    assert client.capture_enabled is True, "Ctrl+Alt+F8 again should resume capture"

    print("  [PASS] Hotkey pause cleanly neutralized all held keys and toggled capture.")


async def test_websocket_handoff_and_stale_protection():
    print("\n" + "=" * 70)
    print("  TEST 5: Live WebSocket Handoff & Stale Disconnect Immunity")
    print("=" * 70)

    config = uvicorn.Config(app=app, host="127.0.0.1", port=8777, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())
    await asyncio.sleep(0.5)

    uri = "ws://127.0.0.1:8777/ws/player"

    try:
        # 1. Connect Client A (Browser)
        ws_a = await websockets.connect(uri)
        await ws_a.send(json.dumps({
            "type": "join",
            "slot_id": 1,
            "name": "Browser Player",
            "code": slot_manager.room_code
        }))
        resp_a = json.loads(await ws_a.recv())
        assert resp_a.get("type") == "joined"
        assert slot_manager.slots[1].friend_name == "Browser Player"
        assert slot_manager.slots[1].websocket is not None
        server_ws_a = slot_manager.slots[1].websocket
        print("  [PASS] Client A (Browser) joined Slot 1.")

        # 2. Connect Client B (Native Background Helper) -> Takes over Slot 1
        ws_b = await websockets.connect(uri)
        await ws_b.send(json.dumps({
            "type": "join",
            "slot_id": 1,
            "name": "Native Helper",
            "code": slot_manager.room_code,
            "source": "background_keyboard_helper"
        }))
        resp_b = json.loads(await ws_b.recv())
        assert resp_b.get("type") == "joined"
        assert slot_manager.slots[1].friend_name == "Native Helper"
        assert slot_manager.slots[1].websocket is not server_ws_a
        server_ws_b = slot_manager.slots[1].websocket
        print("  [PASS] Client B (Helper) took over Slot 1.")

        # 3. Send stale input packet from Client A -> Must be ignored
        stale_packet = build_packet({"KeyS"}, 100)
        await ws_a.send(json.dumps(stale_packet))
        await asyncio.sleep(0.05)
        # Verify Slot 1 did not register Client A's packet
        assert slot_manager.slots[1].last_state["axes"]["ly"] != -1.0, "Stale Client A input was not ignored"
        print("  [PASS] Stale input from older Client A was ignored by server.")

        # 4. Disconnect Client A (Browser closes)
        await ws_a.close()
        await asyncio.sleep(0.05)

        # 5. Verify Slot 1 is STILL ACTIVE with Client B
        slot = slot_manager.slots[1]
        assert slot.is_active is True, "Slot 1 was prematurely detached when older Client A closed"
        assert slot.websocket is server_ws_b, "Slot 1 websocket lost Client B reference"
        print("  [PASS] Slot 1 remained active with Client B after Client A closed.")

        # 6. Send active input packet from Client B
        active_packet = build_packet({"KeyW", "KeyD", "Space"}, 1)
        await ws_b.send(json.dumps(active_packet))
        await asyncio.sleep(0.05)

        assert slot.last_state["axes"]["ly"] == 1.0
        assert slot.last_state["axes"]["lx"] == 1.0
        assert slot.last_state["buttons"]["A"] is True
        print("  [PASS] Client B input packet successfully processed by slot.")

        # 7. Disconnect Client B -> Clean Detach
        await ws_b.close()
        await asyncio.sleep(0.05)
        assert slot.is_active is False
        assert slot.websocket is None
        print("  [PASS] Clean detachment when active Client B disconnected.")

    finally:
        server.should_exit = True
        await server_task


async def test_server_background_capture_api():
    print("\n" + "=" * 70)
    print("  TEST 6: Server Background Capture REST API & Process Lifecycle")
    print("=" * 70)

    from config import config as router_config
    old_port = router_config.port
    router_config.port = 8778

    config = uvicorn.Config(app=app, host="127.0.0.1", port=8778, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())
    await asyncio.sleep(0.5)

    try:
        import urllib.request

        def http_get(path):
            with urllib.request.urlopen(f"http://127.0.0.1:8778{path}") as response:
                return json.loads(response.read().decode())

        def http_post(path, data):
            req = urllib.request.Request(
                f"http://127.0.0.1:8778{path}",
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode())

        # 1. Check initial status
        data = await asyncio.to_thread(http_get, "/api/background-capture/status")
        assert data["running"] is False
        print("  [PASS] Initial background capture status is running=False.")

        # 2. Case A: Start background capture via POST with Local LAN URL
        data_start_local = await asyncio.to_thread(http_post, "/api/background-capture", {
            "play_url": f"http://127.0.0.1:8778/play?code={slot_manager.room_code}",
            "slot_id": 1,
            "name": "Local Tester",
            "enabled": True
        })
        assert data_start_local["ok"] is True
        assert data_start_local["running"] is True
        await asyncio.sleep(0.5)

        res_state_local = await asyncio.to_thread(http_get, "/api/background-capture/input-state?slot_id=1")
        assert res_state_local["running"] is True
        assert res_state_local["ready"] is True
        print("  [PASS] Case A (Local LAN URL): Helper connects directly and reports verified ready.")

        # Stop Case A helper
        await asyncio.to_thread(http_post, "/api/background-capture", {"enabled": False, "slot_id": 1})
        await asyncio.sleep(0.2)

        # 3. Case B: Start background capture via POST with Public Cloudflare Tunnel URL
        # Even when the browser page originated from https://xxx.trycloudflare.com/play,
        # the server must launch the native companion via local loopback to avoid tunnel proxying.
        data_start_cf = await asyncio.to_thread(http_post, "/api/background-capture", {
            "play_url": f"https://prisoners-senators-crucial-ips.trycloudflare.com/play?code={slot_manager.room_code}",
            "slot_id": 1,
            "name": "Cloudflare Tester",
            "enabled": True
        })
        assert data_start_cf["ok"] is True
        assert data_start_cf["running"] is True
        await asyncio.sleep(0.5)

        res_state_cf = await asyncio.to_thread(http_get, "/api/background-capture/input-state?slot_id=1")
        assert res_state_cf["running"] is True
        assert res_state_cf["ready"] is True
        assert slot_manager.slots[1].is_active is True
        print("  [PASS] Case B (Cloudflare Public URL): Helper correctly routes via local loopback and verifies ready.")

        # 4. Stop background capture via POST
        data_stop = await asyncio.to_thread(http_post, "/api/background-capture", {
            "slot_id": 1,
            "enabled": False
        })
        assert data_stop["ok"] is True
        assert data_stop["running"] is False
        print("  [PASS] Successfully stopped background capture helper process via API.")

        await asyncio.sleep(0.2)
        res_final = await asyncio.to_thread(http_get, "/api/background-capture/status")
        assert res_final["running"] is False

        res_state_stopped = await asyncio.to_thread(http_get, "/api/background-capture/input-state?slot_id=1")
        assert res_state_stopped["running"] is False
        assert res_state_stopped["active_keys"] == []
        print("  [PASS] /api/background-capture/input-state cleanly clears active keys when stopped.")

        # 5. Remote Cloudflare-style helper: no host-local helper process exists.
        # The slot itself must still expose fresh background-native telemetry so
        # the remote player's browser can mirror held keys while unfocused.
        remote_ws = await websockets.connect("ws://127.0.0.1:8778/ws/player")
        await remote_ws.send(json.dumps({
            "type": "join",
            "slot_id": 1,
            "name": "Remote Cloudflare Player",
            "code": slot_manager.room_code,
            "source": "background_keyboard_helper",
        }))
        remote_join = json.loads(await remote_ws.recv())
        assert remote_join.get("type") == "joined"

        await remote_ws.send(json.dumps(build_packet({"KeyA", "Space"}, 1)))
        await asyncio.sleep(0.05)

        remote_state = await asyncio.to_thread(http_get, "/api/background-capture/input-state?slot_id=1")
        assert remote_state["running"] is False
        assert remote_state["ready"] is False
        assert remote_state["background_active"] is True
        assert set(remote_state["active_keys"]) == {"KeyA", "Space"}
        print("  [PASS] Remote helper telemetry works without any host-local helper process.")

        await remote_ws.close()
        await asyncio.sleep(0.1)
        remote_state_closed = await asyncio.to_thread(http_get, "/api/background-capture/input-state?slot_id=1")
        assert remote_state_closed["background_active"] is False
        print("  [PASS] Remote helper disconnect clears slot-local background state.")

    finally:
        server.should_exit = True
        await server_task


def main():
    test_key_mappings_and_punctuation()
    test_packet_generation_and_socd()
    test_url_parser()
    test_pause_hotkey_logic()
    asyncio.run(test_websocket_handoff_and_stale_protection())
    asyncio.run(test_server_background_capture_api())
    print("\n" + "=" * 70)
    print("  >>> ALL BACKGROUND KEYBOARD HELPER TESTS PASSED! <<<")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
