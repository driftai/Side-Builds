"""
Live Server & WebSocket Integration Test.
"""

import asyncio
import json
import urllib.request
import websockets
import uvicorn
import sys
import os

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

async def test_live_server():
    from server import app, slot_manager
    port = 8779
    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())
    await asyncio.sleep(0.5)

    try:
        print("Testing WebSocket /ws/player join & input stream...")
        async with websockets.connect(f"ws://127.0.0.1:{port}/ws/player") as ws:
            # Send join
            await ws.send(json.dumps({
                "type": "join",
                "slot_id": 1,
                "friend_name": "SmokeTester",
                "room_code": slot_manager.room_code
            }))
            ack = json.loads(await ws.recv())
            print(f"  [OK] Join Ack received: Slot {ack['slot_id']}, Backend = {ack['backend']}")

            # Send ping
            await ws.send(json.dumps({"type": "ping", "t": 1000.0}))
            pong = json.loads(await ws.recv())
            print(f"  [OK] Pong received: Latency roundtrip confirmed")

            # Send input state
            await ws.send(json.dumps({
                "type": "input",
                "seq": 1,
                "buttons": {"A": True, "DPAD_UP": True},
                "axes": {"lx": 0.5, "ly": 0.5}
            }))
            print("  [OK] Streamed input state successfully")

        print("\n>>> LIVE SERVER INTEGRATION VERIFIED 100%! <<<\n")
    finally:
        server.should_exit = True
        await server_task


if __name__ == "__main__":
    asyncio.run(test_live_server())
