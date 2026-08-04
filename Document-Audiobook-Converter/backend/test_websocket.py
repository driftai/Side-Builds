#!/usr/bin/env python3
"""
Simple WebSocket test client to diagnose connection issues.
Run this to test if the server is working correctly.
"""

import asyncio
import websockets
import json
import time

async def test_websocket_connection():
    """Test WebSocket connection to the Gemini server."""
    uri = "ws://localhost:9083"

    try:
        print("Connecting to WebSocket server...")
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to server")

            # Send configuration
            config = {
                "type": "init",
                "voice": "Aoede",
                "model": "gemini-2.5-flash-preview-native-audio-dialog",
                "allowModelOverride": True,
                "apiKey": "test_key",
                "instructions": "Test connection",
                "sequentialAudioPlay": False
            }

            print("Sending configuration...")
            await websocket.send(json.dumps(config))
            print("✅ Configuration sent")

            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10)
                data = json.loads(response)
                print(f"✅ Received response: {data.get('text', 'unknown')}")

                # Wait a bit to see if more messages come
                print("Waiting for additional messages (10 seconds)...")
                start_time = time.time()

                while time.time() - start_time < 10:
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=1)
                        data = json.loads(response)
                        print(f"📨 Message: {data.get('text', 'unknown')}")
                    except asyncio.TimeoutError:
                        print(".", end="", flush=True)
                        continue

                print("\n✅ Test completed successfully - connection remained open")

            except asyncio.TimeoutError:
                print("❌ Timeout waiting for server response")
            except Exception as e:
                print(f"❌ Error receiving response: {e}")

    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ Connection closed: {e.code} - {e.reason}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    print("WebSocket Connection Test")
    print("=" * 30)
    asyncio.run(test_websocket_connection())
