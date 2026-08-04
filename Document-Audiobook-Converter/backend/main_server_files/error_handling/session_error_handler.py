import json
import asyncio
import websockets
import traceback
from datetime import datetime
from typing import Optional, Any, Dict
from .session_initialization_handler import handle_session_initialization_error
from .api_error_handler import APIErrorHandler

class SessionErrorHandler:
    def __init__(self, connection_monitor, connection_id: int, api_error_handler_instance: APIErrorHandler):
        self.connection_monitor = connection_monitor
        self.connection_id = connection_id
        self.api_error_handler = api_error_handler_instance

    async def handle_timeout_error(self) -> None:
        """Handle timeout errors during session initialization."""
        print(f"Timeout waiting for initial configuration for connection: {self.connection_id}")
        try:
            if self.connection_monitor.is_websocket_open():
                await self.connection_monitor.safe_send(json.dumps({
                    "text": "Connection timeout. Please refresh and try again.",
                    "is_system_message": True,
                    "is_error": True
                }))
        except:
            pass

    async def handle_connection_closed(self, error: websockets.exceptions.ConnectionClosed) -> None:
        """Handle websocket connection closed errors."""
        print(f"Connection {self.connection_id} closed during initialization: {error.code} - {error.reason}")
        if error.code == 1005:
            print("This is a 'No Status Received' error, which typically occurs when a client disconnects unexpectedly")

    async def handle_session_error(self, error: Exception) -> None:
        """Handle general session initialization errors."""
        await handle_session_initialization_error(error, str(self.connection_id), self.connection_monitor.safe_send, self.api_error_handler)

    async def handle_session_tasks_error(self, error: Exception, tasks_to_cancel: list) -> None:
        """Handle errors in session tasks and cancel pending tasks."""
        print(f"Error in session tasks for connection {self.connection_id}: {error}")
        for task in tasks_to_cancel:
            if not task.done():
                task.cancel()

    async def send_session_closed_message(self) -> None:
        """Send session closed message to client."""
        try:
            if self.connection_monitor.is_websocket_open():
                await self.connection_monitor.safe_send(json.dumps({
                    "text": "Session closed",
                    "is_system_message": True
                }))
        except Exception as e:
            print(f"Error sending session closed message for connection {self.connection_id}: {e}")

    async def handle_session_slot_error(self, error_type: str, max_sessions: Optional[int] = None) -> None:
        """Handle errors related to session slot acquisition."""
        messages = {
            "max_reached": f"Server is at maximum capacity ({max_sessions} concurrent sessions). Please wait or try again later.",
            "timeout": "Timeout waiting for an available session. Please try again later.",
            "closed_before_acquire": "Connection closed before acquiring session slot.",
            "acquire_error": "Error acquiring session slot. Please try again."
        }
        
        error_message = messages.get(error_type, "Unknown session slot error")
        print(f"{error_message} Connection: {self.connection_id}")
        
        if self.connection_monitor.is_websocket_open():
            await self.connection_monitor.safe_send(json.dumps({
                "text": error_message,
                "is_system_message": True,
                "is_error": True
            }))

    async def handle_voice_config_timeout(self) -> None:
        """Handle timeout while waiting for voice configuration."""
        print("Timeout waiting for voice configuration")
        try:
            if self.connection_monitor.is_websocket_open():
                await self.connection_monitor.safe_send(json.dumps({
                    "text": "Timeout waiting for voice configuration. Please try again.",
                    "is_system_message": True,
                    "is_error": True
                }))
        except:
            pass

    async def handle_voice_change_error(self, error: Exception) -> None:
        """Handle errors during voice configuration change."""
        print(f"Error processing voice change: {error}")
        try:
            if self.connection_monitor.is_websocket_open():
                await self.connection_monitor.safe_send(json.dumps({
                    "text": f"Error processing voice change: {str(error)}",
                    "is_system_message": True,
                    "is_error": True
                }))
        except:
            pass

    async def handle_session_close_error(self, error: Exception) -> None:
        """Handle errors when closing an existing session."""
        print(f"Error closing existing session: {error}")

    async def handle_model_validation_error(self, error_message: str) -> None:
        """Handle model validation errors."""
        print(f"Model validation error for connection {self.connection_id}: {error_message}")
        try:
            if self.connection_monitor.is_websocket_open():
                await self.connection_monitor.safe_send(json.dumps({
                    "text": f"Configuration error: {error_message}",
                    "is_system_message": True,
                    "is_error": True
                }))
        except Exception as e:
            print(f"Error sending model validation error message for connection {self.connection_id}: {e}")

    async def send_text_part_string(self, text_part_string: str) -> None:
        """Send text part string to client."""
        try:
            if self.connection_monitor.is_websocket_open():
                await self.connection_monitor.safe_send(json.dumps({
                    "text": text_part_string,
                    "is_system_message": True
                }))
        except Exception as e:
            print(f"Error sending text part string for connection {self.connection_id}: {e}")

    async def send_image_part_string(self, image_part_string: str) -> None:
        """Send image part string to client."""
        try:
            if self.connection_monitor.is_websocket_open():
                await self.connection_monitor.safe_send(json.dumps({
                    "text": image_part_string,
                    "is_system_message": True
                }))
        except Exception as e:
            print(f"Error sending image part string for connection {self.connection_id}: {e}")

    async def send_text_part_stream(self, text_part_stream: bytes) -> None:
        """Send text part stream to client."""
        try:
            if self.connection_monitor.is_websocket_open():
                await self.connection_monitor.safe_send(text_part_stream)
        except Exception as e:
            print(f"Error sending text part stream for connection {self.connection_id}: {e}")

    async def send_image_part_stream(self, image_part_stream: bytes) -> None:
        """Send image part stream to client."""
        try:
            if self.connection_monitor.is_websocket_open():
                await self.connection_monitor.safe_send(image_part_stream)
        except Exception as e:
            print(f"Error sending image part stream for connection {self.connection_id}: {e}") 