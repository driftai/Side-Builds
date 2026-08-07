"""Ownership and task lifecycle for an already configured Gemini session."""

import asyncio
import datetime
import json

from main_server_files.response_processing.response_stream_handler import (
    receive_from_gemini,
)
from main_server_files.session_management.gemini_session_initializer import (
    initialize_gemini_session,
)
from main_server_files.session_management.keep_alive_manager import KeepAliveManager
from main_server_files.session_management.session_manager import active_sessions
from main_server_files.websocket_server.message_processor import send_to_gemini


async def run_connected_session(
    websocket,
    connection_id,
    connection_monitor,
    error_handler,
    audio_processor,
    monitor_task,
    prepared,
    session_client,
):
    """Open the Live context and retain the original task creation/cleanup order."""
    async with session_client.aio.live.connect(
        model=prepared.model_name,
        config=prepared.gemini_config,
    ) as session:
        print(
            f"Connected to Gemini API with voice: {prepared.voice_name} "
            f"using model: {prepared.model_name}"
        )
        if prepared.instructions and prepared.instructions.strip():
            print(
                "System instructions configured in session: "
                f"{prepared.instructions[:100]}..."
            )

        active_sessions[connection_id] = {
            "session": session,
            "voice_name": prepared.voice_name,
            "connected_at": datetime.datetime.now().isoformat(),
            "client": session_client,
        }
        print(f"Active sessions: {len(active_sessions)}")

        await connection_monitor.safe_send(json.dumps({
            "text": "Connected to Gemini API - ready for text input",
            "is_system_message": True,
        }))
        await connection_monitor.safe_send(json.dumps({
            "text": (
                "IMPORTANT: Keep this connection open to send text messages. "
                "The session will remain active."
            ),
            "is_system_message": True,
            "connection_guidance": True,
        }))

        audio_processor.is_sequential = prepared.data.get(
            "sequentialAudioPlay", False,
        )
        print(
            "Sequential audio playback "
            f"{'enabled' if audio_processor.is_sequential else 'disabled'} "
            f"for connection {connection_id}"
        )

        keep_alive_manager = KeepAliveManager(
            websocket, connection_id, connection_monitor,
        )
        await keep_alive_manager.start_keep_alive()

        audio_queue_task = asyncio.create_task(
            audio_processor.process_audio_queue(),
        )
        connection_recovery_task = asyncio.create_task(
            connection_monitor.monitor_connection_recovery(),
        )
        send_task = asyncio.create_task(send_to_gemini(
            session,
            websocket,
            connection_monitor,
            connection_id,
            audio_processor,
            session_client,
        ))
        receive_task = asyncio.create_task(receive_from_gemini(
            session=session,
            websocket=websocket,
            connection_monitor=connection_monitor,
            connection_id=connection_id,
            audio_processor=audio_processor,
            voice_name=prepared.voice_name,
            client=session_client,
            initialize_gemini_session=initialize_gemini_session,
        ))

        watched_tasks = [
            send_task,
            receive_task,
            monitor_task,
            connection_recovery_task,
        ]
        try:
            done, pending = await asyncio.wait(
                watched_tasks,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                if task.exception():
                    print(
                        f"Task failed with exception for connection "
                        f"{connection_id}: {task.exception()}"
                    )
                    for pending_task in pending:
                        pending_task.cancel()
                    break
        except Exception as error:
            await error_handler.handle_session_tasks_error(
                error, watched_tasks,
            )
        finally:
            keep_alive_manager.stop()
            audio_queue_task.cancel()

            if not send_task.done():
                send_task.cancel()
            if not receive_task.done():
                receive_task.cancel()
            if not monitor_task.done():
                monitor_task.cancel()
            if not connection_recovery_task.done():
                connection_recovery_task.cancel()

            await error_handler.send_session_closed_message()
