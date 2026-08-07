"""Stable websocket entrypoint for one Gemini Live session."""

import asyncio
import json
import time

import websockets

from main_server_files.audio_processing.audio_processor import AudioProcessor
from main_server_files.error_handling import api_error_handler
from main_server_files.error_handling.session_error_handler import SessionErrorHandler
from main_server_files.session_management.connection_monitor import ConnectionMonitor
from main_server_files.session_management.session_manager import (
    cleanup_resources,
    register_active_session,
    semaphore_acquired,
    session_semaphore,
    update_session_activity,
)
from main_server_files.websocket_server.session_handshake import (
    acquire_connection_slot,
    initialize_session_client,
    prepare_configuration,
    receive_initial_configuration,
)
from main_server_files.websocket_server.session_runtime import (
    run_connected_session,
)


async def gemini_session_handler(websocket):
    """Handle the interaction with Gemini API within a websocket session."""
    connection_id = id(websocket)
    print(f"New connection established: {connection_id}")
    has_semaphore = False

    register_active_session(connection_id, websocket)
    connection_monitor = ConnectionMonitor(
        websocket=websocket,
        connection_id=connection_id,
        update_activity_callback=lambda: update_session_activity(connection_id),
    )

    session_start_time = time.time()
    print(f"Session {connection_id} started at {time.ctime(session_start_time)}")

    audio_processor = AudioProcessor(
        websocket,
        connection_id,
        None,
        update_activity_callback=connection_monitor.record_activity,
    )
    error_handler = SessionErrorHandler(
        connection_monitor,
        connection_id,
        api_error_handler,
    )
    monitor_task = asyncio.create_task(
        connection_monitor.monitor_connection(),
    )

    try:
        slot = await acquire_connection_slot(
            connection_id,
            connection_monitor,
            error_handler,
        )
        has_semaphore = slot.acquired
        if not slot.proceed:
            return

        initial = await receive_initial_configuration(
            websocket,
            connection_monitor,
            connection_id,
            error_handler,
        )
        if not initial.proceed:
            return

        prepared = await prepare_configuration(initial.data, error_handler)
        if prepared is None:
            return

        await connection_monitor.safe_send(json.dumps({
            "text": "Connecting to Gemini API...",
            "is_system_message": True,
        }))

        try:
            print(f"Connecting to Gemini API for connection: {connection_id}")
            print(
                f"Using configuration with voice: {prepared.voice_name} "
                f"and instructions: {bool(prepared.instructions)}"
            )
            session_client = initialize_session_client(prepared)
            audio_processor.client = session_client

            await run_connected_session(
                websocket,
                connection_id,
                connection_monitor,
                error_handler,
                audio_processor,
                monitor_task,
                prepared,
                session_client,
            )
        except Exception as error:
            await error_handler.handle_session_error(error)
            return
    except asyncio.TimeoutError:
        await error_handler.handle_timeout_error()
    except websockets.exceptions.ConnectionClosed as error:
        await error_handler.handle_connection_closed(error)
    except Exception as error:
        await error_handler.handle_session_error(error)
    finally:
        session_duration = time.time() - session_start_time
        print(
            f"Session {connection_id} ended after {session_duration:.1f} seconds"
        )
        if session_duration < 60:
            print(
                f"WARNING: Session {connection_id} was very short "
                f"({session_duration:.1f}s). Check frontend connection handling."
            )

        if has_semaphore:
            session_semaphore.release()
            semaphore_acquired.discard(connection_id)
            print(f"Released semaphore for connection {connection_id}")
        await cleanup_resources(connection_id)
        print(f"Connection {connection_id} handler completed")
