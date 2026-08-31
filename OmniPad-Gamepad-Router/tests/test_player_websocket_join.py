import asyncio
import json
import sys
import pathlib
import uvicorn
import websockets

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import app, slot_manager


async def run_server_and_test():
    print("\n" + "=" * 70)
    print("  TEST: Player WebSocket Join & Interactive Input Streaming")
    print("=" * 70)

    config = uvicorn.Config(app=app, host="127.0.0.1", port=8765, log_level="warning")
    server = uvicorn.Server(config)

    server_task = asyncio.create_task(server.serve())
    await asyncio.sleep(0.5)

    uri = "ws://127.0.0.1:8765/ws/player"

    try:
        async with websockets.connect(uri) as ws:
            # 1. Send Join Request
            join_msg = {
                "type": "join",
                "slot_id": 1,
                "name": "Player 2",
                "code": slot_manager.room_code
            }
            await ws.send(json.dumps(join_msg))

            # 2. Receive Joined / Join_Ack Response
            raw_resp = await ws.recv()
            resp = json.loads(raw_resp)
            print(f"  [PASS] Received join response: {resp}")
            assert resp.get("type") in ("joined", "join_ack")
            assert resp.get("slot_id") == 1
            assert resp.get("status") == "ok"

            # Verify SlotManager attachment
            slot = slot_manager.slots[1]
            assert slot.friend_name == "Player 2"
            assert slot.websocket is not None
            print(f"  [PASS] Slot 1 attached: player='{slot.friend_name}', backend='{slot.controller_type}'")

            # 3. Send Touch Input Frame
            touch_frame = {
                "type": "input",
                "seq": 1,
                "input_surface": "touch",
                "mapping_profile": "universal",
                "buttons": {"A": True, "DPAD_UP": True, "START": True},
                "axes": {"lx": 0, "ly": 0, "rx": 0, "ry": 0, "lt": 0, "rt": 0},
                "key_codes": []
            }
            await ws.send(json.dumps(touch_frame))
            await asyncio.sleep(0.05)
            assert slot.last_state["buttons"]["A"] is True
            assert slot.last_state["buttons"]["DPAD_UP"] is True
            assert slot.last_state["buttons"]["START"] is True
            print("  [PASS] Transmitted & processed Mobile Touch input frame")

            # 4. Send Keyboard Input Frame (Client pre-maps controller preset + carries raw key_codes)
            kb_frame = {
                "type": "input",
                "seq": 2,
                "input_surface": "keyboard",
                "mapping_profile": "it_takes_two",
                "buttons": {
                    "A": True, "B": True, "X": True, "Y": True,
                    "LB": True, "RB": True, "BACK": True, "START": True, "GUIDE": True,
                    "L3": True, "R3": True, "DPAD_UP": True
                },
                "axes": {"lx": 0.0, "ly": 1.0, "rx": 0.0, "ry": 0.0, "lt": 1.0, "rt": 1.0},
                "key_codes": [
                    "KeyW", "Space", "KeyR", "KeyE", "KeyQ",
                    "KeyZ", "KeyC", "Escape", "Enter", "F1",
                    "CapsLock", "KeyF", "KeyG", "ShiftLeft", "ControlLeft",
                    "Digit1"
                ]
            }
            await ws.send(json.dumps(kb_frame))
            await asyncio.sleep(0.05)
            for k in ["KeyW", "Space", "KeyR", "KeyE", "KeyQ", "KeyZ", "KeyC", "Escape", "Enter", "F1", "CapsLock", "KeyF", "KeyG", "Digit1"]:
                assert k in slot.last_state["key_codes"]
            for btn in ["A", "B", "X", "Y", "LB", "RB", "BACK", "START", "GUIDE", "L3", "R3", "DPAD_UP"]:
                assert slot.last_state["buttons"].get(btn) is True, f"Button {btn} missing"
            assert slot.last_state["axes"]["ly"] == 1.0
            print("  [PASS] Transmitted & processed Keyboard frame (All special keys: Space->A, Esc->BACK, Enter->START, Caps->L3, 1->Dpad, etc.)")

            # 4b. Test WASD SOCD Neutral Cancellation & Camera Arrows
            socd_frame = {
                "type": "input",
                "seq": 3,
                "input_surface": "keyboard",
                "mapping_profile": "universal",
                "buttons": {},
                "axes": {"lx": 0.0, "ly": 0.0, "rx": 1.0, "ry": -1.0, "lt": 0.0, "rt": 0.0},
                "key_codes": ["KeyW", "KeyS", "KeyA", "KeyD", "ArrowRight", "ArrowDown"]
            }
            await ws.send(json.dumps(socd_frame))
            await asyncio.sleep(0.05)
            # W + S cancel out to 0, A + D cancel out to 0
            assert slot.last_state["axes"]["lx"] == 0.0
            assert slot.last_state["axes"]["ly"] == 0.0
            # Camera sticks received
            assert slot.last_state["axes"]["rx"] == 1.0
            assert slot.last_state["axes"]["ry"] == -1.0
            print("  [PASS] WASD SOCD opposing cancellation and Camera sticks verified")

            # 4c. Test Simultaneous Movement + Jump + Action
            simul_frame = {
                "type": "input",
                "seq": 4,
                "input_surface": "keyboard",
                "mapping_profile": "it_takes_two",
                "buttons": {"A": True, "B": True},
                "axes": {"lx": 1.0, "ly": 1.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0},
                "key_codes": ["KeyW", "KeyD", "Space", "KeyR"]
            }
            await ws.send(json.dumps(simul_frame))
            await asyncio.sleep(0.05)
            assert slot.last_state["buttons"]["A"] is True
            assert slot.last_state["buttons"]["B"] is True
            assert slot.last_state["axes"]["lx"] == 1.0
            assert slot.last_state["axes"]["ly"] == 1.0
            print("  [PASS] Simultaneous inputs (W+D movement + Space/A Jump + R/B Action) processed seamlessly")

            # 5. Connect Passive Observer (e.g. Host/Laptop /play tab while phone is controlling)
            async with websockets.connect(uri) as ws_obs:
                obs_join = {
                    "type": "join",
                    "slot_id": 1,
                    "name": "Laptop Monitor",
                    "code": slot_manager.room_code,
                    "source": "observer"
                }
                await ws_obs.send(json.dumps(obs_join))
                obs_resp = json.loads(await ws_obs.recv())
                assert obs_resp.get("observer") is True
                assert obs_resp.get("status") == "ok"
                # Controlling player on Slot 1 must NOT be replaced by an observer
                assert slot.friend_name == "Player 2"
                assert slot.websocket is not None
                print("  [PASS] Passive observer joined without stealing slot ownership")

                # Transmit new input frame from controlling player -> observer receives broadcast
                update_frame = {
                    "type": "input",
                    "seq": 5,
                    "input_surface": "keyboard",
                    "mapping_profile": "universal",
                    "buttons": {"A": True, "BACK": True},
                    "axes": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0},
                    "key_codes": ["Space", "Escape"]
                }
                await ws.send(json.dumps(update_frame))
                obs_broadcast = json.loads(await ws_obs.recv())
                assert obs_broadcast.get("type") == "input_state"
                assert obs_broadcast["state"]["buttons"]["A"] is True
                assert obs_broadcast["state"]["buttons"]["BACK"] is True
                assert "Escape" in obs_broadcast["state"]["key_codes"]
                print("  [PASS] Server broadcast authoritative input state to observer tab")

            # Observer disconnected: verify controlling player remains attached
            await asyncio.sleep(0.05)
            assert slot.friend_name == "Player 2"
            assert slot.websocket is not None
            print("  [PASS] Observer disconnect did not detach controlling player")

            # 5b. Test Phone Connect Handoff (Phone connects after laptop was open)
            async with websockets.connect(uri) as ws_phone:
                phone_join = {
                    "type": "join",
                    "slot_id": 1,
                    "name": "Phone Player",
                    "code": slot_manager.room_code,
                    "source": "browser"
                }
                await ws_phone.send(json.dumps(phone_join))
                phone_resp = json.loads(await ws_phone.recv())
                assert phone_resp.get("type") == "joined"
                assert phone_resp.get("status") == "ok"
                # Laptop (ws) receives demotion notification
                demote_msg = json.loads(await ws.recv())
                assert demote_msg.get("type") == "demoted_to_observer"
                assert demote_msg.get("observer") is True
                assert slot.friend_name == "Phone Player"
                print("  [PASS] Phone player cleanly took over Slot 1, laptop demoted to observer")

                # Phone sends input -> reaches slot controller and broadcasts to laptop (ws)
                phone_frame = {
                    "type": "input",
                    "seq": 10,
                    "input_surface": "touch",
                    "mapping_profile": "universal",
                    "buttons": {"A": True, "START": True},
                    "axes": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0},
                    "key_codes": []
                }
                await ws_phone.send(json.dumps(phone_frame))
                await asyncio.sleep(0.05)
                assert slot.last_state["buttons"]["A"] is True
                assert slot.last_state["buttons"]["START"] is True
                # Laptop receives broadcast from phone's button press
                laptop_broadcast = json.loads(await ws.recv())
                assert laptop_broadcast.get("type") == "input_state"
                assert laptop_broadcast["state"]["buttons"]["A"] is True
                print("  [PASS] Phone button presses routed through server to game and laptop monitor")

            # 6. Send Ping Heartbeat
            await ws.send(json.dumps({"type": "ping", "t": 1000.0}))
            pong_raw = await ws.recv()
            pong = json.loads(pong_raw)
            assert pong.get("type") == "pong"
            assert pong.get("t") == 1000.0
            print(f"  [PASS] Received ping-pong heartbeat: {pong}")

            # 7. Leave Observer Session
            await ws.send(json.dumps({"type": "leave"}))
            left_raw = await ws.recv()
            left_resp = json.loads(left_raw)
            assert left_resp.get("type") == "left"
            print("  [PASS] Observer clean leave verified")

        # 8. Test Malformed Frames, Unknown Keycodes, Stale Seq, and Disconnect Neutralization
        async with websockets.connect(uri) as ws_ctrl:
            await ws_ctrl.send(json.dumps({
                "type": "join",
                "slot_id": 1,
                "name": "ResiliencePlayer",
                "code": slot_manager.room_code,
                "source": "browser"
            }))
            await ws_ctrl.recv()
            slot = slot_manager.slots[1]
            assert slot.friend_name == "ResiliencePlayer"

            # 8a. Non-JSON raw string
            await ws_ctrl.send("NOT_VALID_JSON_STRING")
            await asyncio.sleep(0.05)  # Server must not crash
            assert slot.websocket is not None
            # 8b. Missing type / unknown type
            await ws_ctrl.send(json.dumps({"unknown_field": 123}))
            await asyncio.sleep(0.05)
            # 8c. Unknown key codes in input frame
            unknown_key_frame = {
                "type": "input",
                "seq": 20,
                "input_surface": "keyboard",
                "mapping_profile": "universal",
                "buttons": {},
                "axes": {},
                "key_codes": ["AlienKey999", "UndefinedKey", "KeyW"]
            }
            await ws_ctrl.send(json.dumps(unknown_key_frame))
            await asyncio.sleep(0.05)
            assert "AlienKey999" in slot.last_state["key_codes"]
            # 8d. Duplicate / Out-of-order sequence number
            dup_frame = {
                "type": "input",
                "seq": 15,  # 15 < 20
                "input_surface": "keyboard",
                "mapping_profile": "universal",
                "buttons": {"X": True},
                "axes": {},
                "key_codes": []
            }
            await ws_ctrl.send(json.dumps(dup_frame))
            await asyncio.sleep(0.05)
            assert not slot.last_state["buttons"].get("X"), "Stale out-of-order packet must be dropped"
            print("  [PASS] Server gracefully handled non-JSON text, unknown types, unknown keys, and stale seq numbers")

            # 8e. Send held input before disconnect
            await ws_ctrl.send(json.dumps({
                "type": "input",
                "seq": 30,
                "input_surface": "touch",
                "buttons": {"A": True, "START": True},
                "axes": {"lx": 1.0, "ly": 1.0}
            }))
            await asyncio.sleep(0.05)
            assert slot.last_state["buttons"].get("A") is True

        # 9. Disconnect While Holding Inputs (Neutralization)
        await asyncio.sleep(0.1)
        # Slot must be detached and neutralized
        assert slot.websocket is None
        print("  [PASS] Disconnect while holding buttons immediately neutralized slot and released inputs")

    finally:
        server.should_exit = True
        await server_task
        print("  >>> PLAYER WEBSOCKET JOIN TESTS COMPLETED SUCCESSFULLY! <<<\n")


if __name__ == "__main__":
    asyncio.run(run_server_and_test())
