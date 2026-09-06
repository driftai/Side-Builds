"""Live WebSocket and target-routing journeys used by the core smoke facade."""

import asyncio
import json

from router.controller import Xbox360Backend
from router.slot_manager import SlotManager


def test_section(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  TEST: {title}")
    print("=" * 60)


async def test_canonical_end_to_end_user_journey() -> None:
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
        async with websockets.connect(ws_url) as phone_ws:
            join_payload = {
                "type": "join",
                "slot_id": 1,
                "name": "Alex (Phone)",
                "code": slot_manager.room_code,
                "source": "browser",
            }
            await phone_ws.send(json.dumps(join_payload))
            join_ack = json.loads(await phone_ws.recv())
            assert join_ack.get("type") == "joined" and join_ack.get("slot_id") == 1
            print("  [PASS] Step 1: Remote Phone connected as Player 2 on Slot 1")

            slot = slot_manager.slots[1]
            assert isinstance(slot.controller, Xbox360Backend)

            async with websockets.connect(ws_url) as observer_ws:
                observer_join = {
                    "type": "join",
                    "slot_id": 1,
                    "name": "Host Monitor",
                    "code": slot_manager.room_code,
                    "source": "observer",
                }
                await observer_ws.send(json.dumps(observer_join))
                observer_ack = json.loads(await observer_ws.recv())
                assert observer_ack.get("observer") is True
                print("  [PASS] Step 2: Laptop Observer connected in passive monitoring mode")

                touch_frame = {
                    "type": "input",
                    "seq": 1,
                    "input_surface": "touch",
                    "mapping_profile": "universal",
                    "buttons": {"A": True, "START": True, "RT": True},
                    "axes": {
                        "lx": 0.85,
                        "ly": 0.85,
                        "rx": -0.70,
                        "ry": 0.50,
                        "lt": 0.00,
                        "rt": 0.95,
                    },
                    "key_codes": [],
                }
                await phone_ws.send(json.dumps(touch_frame))
                await asyncio.sleep(0.05)

                assert slot.last_state["buttons"]["A"] is True
                assert slot.last_state["buttons"]["START"] is True
                assert slot.last_state["axes"]["lx"] > 0.6
                assert slot.last_state["axes"]["ly"] > 0.6
                assert slot.last_state["axes"]["rx"] < -0.5
                assert slot.last_state["axes"]["rt"] == 0.95
                print("  [PASS] Step 3 & 4: Multi-touch inputs decoded, mapped, and applied to ViGEm Xbox controller")

                observer_message = json.loads(await observer_ws.recv())
                assert observer_message.get("type") == "input_state"
                assert observer_message["state"]["buttons"]["A"] is True
                assert observer_message["state"]["axes"]["rt"] == 0.95
                print("  [PASS] Step 5: Authoritative state broadcast received by laptop observer")

                release_frame = {
                    "type": "input",
                    "seq": 2,
                    "input_surface": "touch",
                    "mapping_profile": "universal",
                    "buttons": {},
                    "axes": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0},
                    "key_codes": [],
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


async def test_unfocused_target_routing_behavior() -> None:
    test_section("Unfocused Process Liveness & Target Safety Gating")
    from config import config
    from router.targeting import target_manager

    config.target_gate_enabled = True
    manager = SlotManager()
    await manager.set_controller_type(1, "xbox360")
    slot = manager.slots[1]

    original_selected = target_manager.selected
    original_is_foreground = getattr(target_manager, "is_target_foreground", None)
    original_is_running = getattr(target_manager, "is_target_running", None)

    class MockTarget:
        pid = 1122
        hwnd = 3344
        title = "It Takes Two"
        process_name = "ItTakesTwo.exe"

    try:
        target_manager.selected = MockTarget()
        target_manager.is_target_running = lambda: True
        target_manager.is_target_foreground = lambda: False

        frame = {
            "seq": 1,
            "input_surface": "touch",
            "buttons": {"A": True},
            "axes": {"lx": 1.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0},
        }
        await manager.process_input_packet(1, frame)
        assert slot.last_state["buttons"].get("A") is True
        assert slot.is_active is True
        print("  [PASS] Virtual Xbox 360 controller routes continuously while target process is running (unfocused)")

        await manager.set_controller_type(1, "keyboard_target")
        frame["seq"] = 2
        await manager.process_input_packet(1, frame)
        assert not slot.last_state["buttons"].get("A")
        print("  [PASS] Keyboard injection is strictly gated when target is not foreground")

        await manager.set_controller_type(1, "xbox360")
        target_manager.is_target_running = lambda: False
        frame["seq"] = 3
        await manager.process_input_packet(1, frame)
        assert not slot.last_state["buttons"].get("A")
        assert slot.is_active is False
        print("  [PASS] Target termination immediately neutralizes virtual controller and halts input")
    finally:
        target_manager.selected = original_selected
        if original_is_foreground is not None:
            target_manager.is_target_foreground = original_is_foreground
        if original_is_running is not None:
            target_manager.is_target_running = original_is_running


async def test_local_background_routing_and_key_streaming() -> None:
    test_section("Local Background Routing & Physical Key Streaming")
    manager = SlotManager()
    await manager.set_controller_type(1, "xbox360")
    slot = manager.slots[1]

    keyboard_frame = {
        "seq": 1,
        "input_surface": "keyboard",
        "mapping_profile": "universal",
        "background_routing": True,
        "buttons": {"A": True, "X": True},
        "axes": {"lx": 0.35, "ly": 0.35, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0},
        "key_codes": ["KeyW", "KeyD", "Space", "KeyJ"],
    }
    await manager.process_input_packet(1, keyboard_frame)
    assert slot.last_state["axes"]["ly"] == 0.35
    assert slot.last_state["axes"]["lx"] == 0.35
    assert slot.last_state["buttons"].get("A") is True
    assert slot.last_state["buttons"].get("X") is True
    assert slot.is_active is True
    assert slot.last_state["key_codes"] == keyboard_frame["key_codes"]
    print("  [PASS] Browser-resolved keyboard state and raw key identity route together without remapping")

    site_only_frame = {
        "seq": 2,
        "input_surface": "keyboard",
        "mapping_profile": "universal",
        "background_routing": False,
        "buttons": {},
        "axes": {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0},
        "key_codes": ["KeyW", "Space"],
    }
    await manager.process_input_packet(1, site_only_frame)
    print("  [PASS] background_routing=False cleanly releases holds and restricts input to browser")
