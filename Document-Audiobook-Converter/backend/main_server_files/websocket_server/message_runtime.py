"""Websocket read-loop, reinitialization, and retry supervision."""

import asyncio
import json
import time
import traceback

import websockets

from main_server_files.api_configuration.gemini_config import MAIN_MODEL as MODEL
from main_server_files.chat_history.chat_history_handler import load_chat_history
from main_server_files.session_management.gemini_session_initializer import (
    initialize_gemini_session,
)
from main_server_files.websocket_server.message_dispatch import (
    dispatch_client_message,
)
from main_server_files.websocket_server.websocket_protocol import (
    build_history_context,
)


async def _process_raw_message(
    message,
    session,
    connection_monitor,
    connection_id,
    audio_processor,
):
    """Decode and dispatch one frame while retaining the original error policy."""
    try:
        connection_monitor.record_activity()
        data = json.loads(message)
        print(
            f"Received message from client {connection_id}: "
            f"{data.get('type', 'unknown type')}"
        )
        return await dispatch_client_message(
            data,
            session,
            connection_monitor,
            connection_id,
            audio_processor,
        )
    except json.JSONDecodeError as error:
        print(
            f"ERROR: Failed to decode client message: {error}. "
            f"Raw message: {message[:500]}..."
        )
        try:
            await connection_monitor.safe_send(json.dumps({
                "type": "json_error",
                "message": "Invalid JSON format",
                "error": str(error),
                "timestamp": time.time(),
            }))
        except Exception as send_error:
            print(f"Could not send JSON error response: {send_error}")
    except Exception as error:
        print(f"ERROR: Unhandled exception in message processing loop: {error}")
        traceback.print_exc()
        try:
            await connection_monitor.safe_send(json.dumps({
                "type": "processing_error",
                "message": "Internal processing error",
                "error": str(error),
                "timestamp": time.time(),
            }))
        except Exception as send_error:
            print(f"Could not send error response: {send_error}")
        await asyncio.sleep(1)
    return True


async def _reinitialize_after_message_loop(
    session,
    websocket,
    connection_monitor,
    connection_id,
    client,
):
    """Recreate the compatibility session after a natural websocket iteration."""
    context = build_history_context(load_chat_history())
    voice_name = "Aoede"

    await connection_monitor.safe_send(json.dumps({
        "text": "Reinitializing connection...",
        "is_system_message": True,
    }))

    if not client:
        print("Error: No client instance available for reinitialization")
        await connection_monitor.safe_send(json.dumps({
            "text": "Failed to reinitialize: No client instance available",
            "is_system_message": True,
            "is_error": True,
        }))
        return "no_client", session

    new_session = await initialize_gemini_session(
        client=client,
        voice_name=voice_name,
        context=context,
        websocket=websocket,
        safe_send=connection_monitor.safe_send,
        model=MODEL,
        connection_id=connection_id,
    )
    if new_session:
        print("Successfully reinitialized model")
        await connection_monitor.safe_send(json.dumps({
            "text": "Connection reinitialized successfully",
            "is_system_message": True,
        }))
        return "success", new_session

    print("Failed to reinitialize model")
    await connection_monitor.safe_send(json.dumps({
        "text": "Failed to reinitialize connection",
        "is_system_message": True,
        "is_error": True,
    }))
    return "failed", session


def _log_connection_closed(error, connection_monitor, connection_id):
    print(f"Client connection {connection_id} closed: {error.code} - {error.reason}")
    active_duration = time.time() - connection_monitor.last_activity_time
    print(
        f"Connection was active for: {active_duration:.1f} seconds since last activity"
    )
    if active_duration < 30:
        print(
            f"WARNING: Connection {connection_id} closed prematurely after only "
            f"{active_duration:.1f} seconds!"
        )
        print(
            "This suggests a frontend issue where the client is closing the "
            "connection too early."
        )
        print(
            "The Gemini session was established but the client disconnected "
            "before any user input."
        )
    else:
        print(
            f"Connection {connection_id} lasted {active_duration:.1f} seconds - "
            "may be normal closure"
        )

    if error.code == 1000:
        print(f"Normal connection closure for {connection_id}")
    else:
        print(
            f"Abnormal connection closure for {connection_id} "
            f"(code {error.code}). This may indicate a client issue."
        )


async def run_send_to_gemini(
    session,
    websocket,
    connection_monitor,
    connection_id,
    audio_processor,
    client=None,
):
    """Run the established message loop and its three-attempt supervisor."""
    retry_count = 0
    max_retries = 3

    while retry_count < max_retries:
        try:
            while True:
                print(
                    f"Starting WebSocket message loop for connection {connection_id}"
                )
                try:
                    async for message in websocket:
                        should_continue = await _process_raw_message(
                            message,
                            session,
                            connection_monitor,
                            connection_id,
                            audio_processor,
                        )
                        if not should_continue:
                            return

                    print(
                        "WebSocket message loop finished gracefully. "
                        "Attempting to reinitialize model..."
                    )
                    if websocket.state in (
                        websockets.protocol.State.CLOSED,
                        websockets.protocol.State.CLOSING,
                    ):
                        print("WebSocket is closed, cannot reinitialize")
                        return

                    try:
                        action, reinitialized = await _reinitialize_after_message_loop(
                            session,
                            websocket,
                            connection_monitor,
                            connection_id,
                            client,
                        )
                        if action == "no_client":
                            return
                        if action == "success":
                            session = reinitialized
                            retry_count = 0
                            continue
                    except Exception as error:
                        print(f"Error reinitializing model: {error}")
                        traceback.print_exc()
                        break
                except websockets.exceptions.ConnectionClosed as error:
                    _log_connection_closed(
                        error, connection_monitor, connection_id,
                    )
                    return
                except Exception as error:
                    print(f"ERROR: Unhandled exception in outer message loop: {error}")
                    print(
                        f"Exception occurred "
                        f"{time.time() - connection_monitor.last_activity_time:.1f} "
                        "seconds after last activity"
                    )
                    traceback.print_exc()
                    break
        except Exception as error:
            print(
                "ERROR: Unhandled exception in send_to_gemini task "
                f"(retry loop level): {error}"
            )
            traceback.print_exc()
            retry_count += 1
            if retry_count >= max_retries:
                print(
                    f"ERROR: Failed after {max_retries} retries in "
                    "send_to_gemini. Aborting task."
                )
                break
            print(
                f"Retrying send_to_gemini task "
                f"(attempt {retry_count}/{max_retries})..."
            )
            await asyncio.sleep(2 ** retry_count)

    print(f"send_to_gemini task ended for connection: {connection_id}")
