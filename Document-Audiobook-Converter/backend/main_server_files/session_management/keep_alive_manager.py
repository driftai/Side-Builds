import asyncio
import websockets
from typing import Optional

class KeepAliveManager:
    def __init__(self, websocket: websockets.WebSocketServerProtocol, connection_id: str, connection_monitor):
        self.websocket = websocket
        self.connection_id = connection_id
        self.connection_monitor = connection_monitor
        self.keep_alive_task: Optional[asyncio.Task] = None
        self.ping_interval = 20  # Send ping every 20 seconds

    async def start_keep_alive(self):
        """Start the keep-alive ping task."""
        self.keep_alive_task = asyncio.create_task(self._keep_alive())
        return self.keep_alive_task

    async def _keep_alive(self):
        """Send periodic pings to keep the connection alive."""
        ping_count = 0
        try:
            while True:
                try:
                    # Check if the connection is still open before pinging
                    if not self.connection_monitor.is_websocket_open():
                        print(f"Connection {self.connection_id} is closed, stopping keep-alive")
                        break

                    await self.websocket.ping()
                    ping_count += 1
                    if ping_count % 5 == 0:  # Log every 5 pings
                        print(f"Sent ping #{ping_count} to connection: {self.connection_id}")
                    await asyncio.sleep(self.ping_interval)
                except Exception as e:
                    print(f"Error in keep-alive ping: {e}")
                    break
        except Exception as e:
            print(f"Keep-alive task ended for connection {self.connection_id}: {e}")

    def stop(self):
        """Stop the keep-alive task."""
        if self.keep_alive_task and not self.keep_alive_task.done():
            self.keep_alive_task.cancel() 