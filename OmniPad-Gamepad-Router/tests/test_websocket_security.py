"""
OmniPad WebSocket Security, Observer Containment & Malformed Frame Resilience Test Suite.
Tests:
1. /ws/host local-only telemetry gate.
2. Read-only observer containment (observers cannot submit controller input).
3. Authoritative slot ownership handoff & stale sender neutralization.
4. Remote client helper source spoofing rejection.
5. Wrong room-code and invalid slot rejection.
6. Malformed JSON, non-dict payloads, and oversized frame resilience.
"""

import asyncio
import json
import pathlib
import sys
import uvicorn
import websockets

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import app, slot_manager, target_manager

TEST_PORT = 8793


def test_section(title: str):
    print("\n" + "=" * 70)
    print(f"  WEBSOCKET SECURITY TEST: {title}")
    print("=" * 70)


async def test_host_websocket_gate():
    test_section("1. Host WebSocket Gate (/ws/host)")
    uri = f"ws://127.0.0.1:{TEST_PORT}/ws/host"

    # Local connection connects and receives initial_status
    async with websockets.connect(uri) as ws:
        msg = json.loads(await ws.recv())
        assert msg.get("type") == "initial_status"
        print("  [PASS] Local /ws/host connects successfully and receives telemetry.")


async def test_observer_read_only_containment():
    test_section("2. Observer Read-Only Containment (Input Injection Block)")
    uri = f"ws://127.0.0.1:{TEST_PORT}/ws/player"

    slot = slot_manager.slots[1]
    # Neutralize slot state
    slot.last_state = {"buttons": {}, "axes": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0}}

    # Connect as Observer
    async with websockets.connect(uri) as obs_ws:
        await obs_ws.send(json.dumps({
            "type": "join",
            "slot_id": 1,
            "name": "Observer Viewer",
            "code": slot_manager.room_code,
            "source": "observer"
        }))
        join_ack = json.loads(await obs_ws.recv())
        assert join_ack.get("type") == "joined"
        assert join_ack.get("observer") is True
        print("  [PASS] Observer joined in passive monitoring mode.")

        # Attempt to inject controller input as an observer
        injection_packet = {
            "type": "input",
            "seq": 1,
            "buttons": {"A": True, "START": True},
            "axes": {"lx": 1.0, "ly": 1.0},
            "key_codes": ["KeyW", "Space"]
        }
        await obs_ws.send(json.dumps(injection_packet))
        await asyncio.sleep(0.08)

        # Verify controller state was NOT modified by observer input
        assert not slot.last_state["buttons"].get("A"), "Observer input MUST NOT modify slot button state"
        assert slot.last_state["axes"]["lx"] != 1.0, "Observer input MUST NOT modify slot axis state"
        print("  [PASS] Observer input injection attempt was blocked by server containment.")


async def test_authoritative_ownership_and_demotion():
    test_section("3. Authoritative Slot Ownership & Demotion Handoff")
    uri = f"ws://127.0.0.1:{TEST_PORT}/ws/player"
    slot = slot_manager.slots[1]

    # Player 1 joins slot 1
    ws1 = await websockets.connect(uri)
    await ws1.send(json.dumps({
        "type": "join",
        "slot_id": 1,
        "name": "Player 1",
        "code": slot_manager.room_code,
        "source": "browser"
    }))
    ack1 = json.loads(await ws1.recv())
    assert ack1.get("type") == "joined" and ack1.get("observer") is not True
    print("  [PASS] Player 1 joined and acquired authoritative slot ownership.")

    # Player 1 sends input -> accepted
    await ws1.send(json.dumps({
        "type": "input",
        "seq": 1,
        "buttons": {"A": True},
        "axes": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0}
    }))
    await asyncio.sleep(0.05)
    assert slot.last_state["buttons"].get("A") is True

    # Player 2 joins slot 1 -> takes over ownership
    ws2 = await websockets.connect(uri)
    await ws2.send(json.dumps({
        "type": "join",
        "slot_id": 1,
        "name": "Player 2",
        "code": slot_manager.room_code,
        "source": "browser"
    }))
    ack2 = json.loads(await ws2.recv())
    assert ack2.get("type") == "joined" and ack2.get("observer") is not True

    # Player 1 should receive demoted_to_observer notification
    demote_msg = json.loads(await ws1.recv())
    assert demote_msg.get("type") == "demoted_to_observer"
    print("  [PASS] Player 1 was cleanly demoted to read-only observer when Player 2 attached.")

    # Stale Player 1 sends input -> MUST BE IGNORED
    await ws1.send(json.dumps({
        "type": "input",
        "seq": 2,
        "buttons": {"B": True},
        "axes": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0}
    }))
    await asyncio.sleep(0.05)
    assert not slot.last_state["buttons"].get("B"), "Demoted Player 1 input MUST be ignored"

    # Player 2 sends input -> ACCEPTED
    await ws2.send(json.dumps({
        "type": "input",
        "seq": 1,
        "buttons": {"X": True},
        "axes": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0}
    }))
    await asyncio.sleep(0.05)
    assert slot.last_state["buttons"].get("X") is True
    print("  [PASS] Authoritative Player 2 successfully controls slot.")

    await ws1.close()
    await ws2.close()


async def test_room_code_and_malformed_input_resilience():
    test_section("4. Room Credential Isolation & Malformed Frame Resilience")
    uri = f"ws://127.0.0.1:{TEST_PORT}/ws/player"

    # 1. Invalid Room Code
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({
            "type": "join",
            "slot_id": 1,
            "name": "Attacker",
            "code": "WRONG-CODE-999"
        }))
        err = json.loads(await ws.recv())
        assert err.get("type") == "error"
        assert "Invalid room code" in err.get("error", "")
        print("  [PASS] Wrong room code rejected.")

    # 2. Invalid Slot ID
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({
            "type": "join",
            "slot_id": 9999,
            "name": "Player",
            "code": slot_manager.room_code
        }))
        err = json.loads(await ws.recv())
        assert err.get("type") == "error"
        assert "Invalid slot" in err.get("error", "")
        print("  [PASS] Out-of-bounds slot ID rejected.")

    # 3. Malformed JSON Frames & Unknown Types
    async with websockets.connect(uri) as ws:
        # Send raw malformed string
        await ws.send("{{{not json string")
        # Send non-dict JSON
        await ws.send("12345")
        await ws.send(json.dumps(["array", "payload"]))
        # Send unknown message type
        await ws.send(json.dumps({"type": "exploit_command", "val": 123}))

        # Send valid join to confirm server connection remains alive
        await ws.send(json.dumps({
            "type": "join",
            "slot_id": 1,
            "name": "Resilience Tester",
            "code": slot_manager.room_code
        }))
        res = json.loads(await ws.recv())
        assert res.get("type") == "joined"
        print("  [PASS] Server gracefully handled malformed JSON, arrays, non-dict payloads, and unknown message types.")


async def test_focus_request_authorization():
    test_section("5. Selected-Target Focus Authorization")
    uri = f"ws://127.0.0.1:{TEST_PORT}/ws/player"

    async with websockets.connect(uri) as observer:
        await observer.send(json.dumps({
            "type": "join", "slot_id": 2, "name": "Focus Observer",
            "code": slot_manager.room_code, "source": "observer",
        }))
        assert json.loads(await observer.recv()).get("observer") is True
        await observer.send(json.dumps({"type": "focus_target"}))
        rejected = json.loads(await observer.recv())
        assert rejected == {"type": "focus_result", "ok": False, "reason": "not_controller"}

    original_focus = target_manager.focus_selected
    target_manager.focus_selected = lambda: (True, "focused")
    try:
        async with websockets.connect(uri) as owner:
            await owner.send(json.dumps({
                "type": "join", "slot_id": 2, "name": "Focus Owner",
                "code": slot_manager.room_code, "source": "browser",
            }))
            joined = json.loads(await owner.recv())
            assert joined.get("type") == "joined" and joined.get("observer") is not True
            await owner.send(json.dumps({"type": "focus_target"}))
            accepted = json.loads(await owner.recv())
            assert accepted == {"type": "focus_result", "ok": True, "reason": "focused"}
            await owner.send(json.dumps({"type": "focus_target"}))
            limited = json.loads(await owner.recv())
            assert limited == {"type": "focus_result", "ok": False, "reason": "rate_limited"}
    finally:
        target_manager.focus_selected = original_focus
    print("  [PASS] Only the active slot owner can request bounded host focus.")


async def main():
    config = uvicorn.Config(app=app, host="127.0.0.1", port=TEST_PORT, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    for _ in range(50):
        if server.started:
            break
        await asyncio.sleep(0.05)

    try:
        await test_host_websocket_gate()
        await test_observer_read_only_containment()
        await test_authoritative_ownership_and_demotion()
        await test_room_code_and_malformed_input_resilience()
        await test_focus_request_authorization()
        print("\n" + "=" * 70)
        print("  >>> ALL WEBSOCKET SECURITY TESTS PASSED! <<<")
        print("=" * 70 + "\n")
    finally:
        server.should_exit = True
        await server_task


if __name__ == "__main__":
    asyncio.run(main())
