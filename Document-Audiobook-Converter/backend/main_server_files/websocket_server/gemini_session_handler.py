import asyncio
import json
import datetime
import time
import websockets
from main_server_files.api_configuration.gemini_config import MAIN_MODEL, create_gemini_config
from main_server_files.session_management.session_manager import (
    active_sessions,
    semaphore_acquired,
    session_semaphore,
    cleanup_resources,
    register_active_session,
    update_session_activity,
    MAIN_MODEL_SESSION_LIMIT,
    acquire_session_slot,
    create_gemini_session
)
from main_server_files.audio_processing.audio_processor import AudioProcessor
from main_server_files.session_management.gemini_session_initializer import (
    initialize_gemini_session
)
from main_server_files.websocket_server.message_processor import send_to_gemini
from main_server_files.response_processing.response_stream_handler import receive_from_gemini
from main_server_files.session_management.connection_monitor import ConnectionMonitor
from main_server_files.session_management.keep_alive_manager import KeepAliveManager
from main_server_files.error_handling.session_error_handler import SessionErrorHandler
from main_server_files.error_handling import api_error_handler
from main_server_files.voice_configuration.voice_config_handler import extract_voice_configuration, extract_voice_and_model_configuration
from main_server_files.chat_history.chat_history_handler import load_chat_history, clear_chat_history
from main_server_files.command_processing.command_handler import process_command
from main_server_files.status_monitoring.api_usage_monitor import api_usage_tracker, start_monitoring_service

async def gemini_session_handler(websocket):
    """Handles the interaction with Gemini API within a websocket session.

    Args:
        websocket: The websocket connection
    """
    # Track active connections to help with cleanup
    connection_id = id(websocket)
    print(f"New connection established: {connection_id}")

    # Initialize session variable to None
    session = None

    # Track if we've acquired a semaphore
    has_semaphore = False

    # Register the new session
    register_active_session(connection_id, websocket)

    # Create connection monitor first so we can pass its method
    connection_monitor = ConnectionMonitor(
        websocket=websocket,
        connection_id=connection_id,
        update_activity_callback=lambda: update_session_activity(connection_id)
    )

    # Track session start time for diagnostics
    session_start_time = time.time()
    print(f"Session {connection_id} started at {time.ctime(session_start_time)}")

    # Create audio processor instance, passing the ConnectionMonitor's record_activity method
    # Client will be set later when the model configuration is received
    audio_processor = AudioProcessor(
        websocket,
        connection_id,
        None,  # Client will be set later
        update_activity_callback=connection_monitor.record_activity # Pass the method directly
    )

    # Create error handler instance, passing the imported api_error_handler
    error_handler = SessionErrorHandler(connection_monitor, connection_id, api_error_handler)

    # Start the connection monitor task
    monitor_task = asyncio.create_task(connection_monitor.monitor_connection())

    try:
        # Check if we can acquire a session slot
        if not session_semaphore.locked() and session_semaphore._value <= 0:
            await error_handler.handle_session_slot_error("max_reached", MAIN_MODEL_SESSION_LIMIT)
            return

        # Try to acquire the semaphore with a timeout
        try:
            # Wait up to 30 seconds to acquire a session slot
            acquire_timeout = 30
            acquire_success = False

            # Send a message to the client that they're in queue
            if connection_monitor.is_websocket_open():
                await connection_monitor.safe_send(json.dumps({
                    "text": f"Waiting for an available session slot (timeout: {acquire_timeout}s)...",
                    "is_system_message": True
                }))
            else:
                await error_handler.handle_session_slot_error("closed_before_acquire")
                return

            # Try to acquire the semaphore with a timeout
            try:
                acquire_success = await asyncio.wait_for(session_semaphore.acquire(), timeout=acquire_timeout)
                if acquire_success:
                    # Track that this connection has acquired a semaphore
                    semaphore_acquired.add(connection_id)
                    has_semaphore = True
            except asyncio.TimeoutError:
                acquire_success = False

            if not acquire_success:
                await error_handler.handle_session_slot_error("timeout")
                return

            print(f"Acquired session slot for connection {connection_id}")
            if connection_monitor.is_websocket_open():
                await connection_monitor.safe_send(json.dumps({
                    "text": "Session slot acquired. Proceeding with connection...",
                    "is_system_message": True
                }))
            else:
                print(f"Connection {connection_id} closed after acquiring semaphore")
                await cleanup_resources(connection_id)
                return

        except Exception as e:
            await error_handler.handle_session_slot_error("acquire_error")
            return

        config_message = await asyncio.wait_for(websocket.recv(), timeout=30)
        config_data = json.loads(config_message)
        print(f"Configuration received for connection: {connection_id}")

        # Check if this is a clear history command
        if config_data.get("command") == "clear_history":
            print("Received clear_history command at session start")
            clear_chat_history()
            await connection_monitor.safe_send(json.dumps({
                "text": "Chat history cleared",
                "is_system_message": True
            }))
            # Get the next message which should be the configuration
            config_message = await asyncio.wait_for(websocket.recv(), timeout=30)
            config_data = json.loads(config_message)
            print("Configuration received after history clear")

        # Check if this is a get_history command
        if config_data.get("command") == "get_history":
            print("Received get_history command at session start")
            chat_history = load_chat_history()

            if chat_history:
                await connection_monitor.safe_send(json.dumps({
                    "text": "Restoring chat history...",
                    "is_system_message": True
                }))

                for msg in chat_history:
                    # Format the timestamp
                    timestamp = ""
                    try:
                        # Parse the ISO timestamp and format it
                        dt = datetime.datetime.fromisoformat(msg['timestamp'])
                        timestamp = dt.strftime("%m/%d/%Y %I:%M %p")
                    except Exception as e:
                        print(f"Error formatting timestamp: {e}")

                    prefix = "YOU: " if msg['role'] == 'user' else "GEMINI: "
                    await connection_monitor.safe_send(json.dumps({
                        "text": f"{prefix}{msg['content']}",
                        "timestamp": timestamp,
                        "is_history": True
                    }))
                    await asyncio.sleep(0.1)
            else:
                await connection_monitor.safe_send(json.dumps({
                    "text": "No chat history found",
                    "is_system_message": True
                }))

            # Get the next message which should be the configuration
            config_message = await asyncio.wait_for(websocket.recv(), timeout=30)
            config_data = json.loads(config_message)
            print("Configuration received after history request")

        # Check if this is a voice change command
        if config_data.get("command") == "close_session":
            print("Received close session command - waiting for new voice config")
            try:
                # Add timeout for receiving the next message
                config_message = await asyncio.wait_for(websocket.recv(), timeout=10)
                config_data = json.loads(config_message)
                print("New voice configuration received")

                # Send acknowledgment to client
                await connection_monitor.safe_send(json.dumps({
                    "text": "Voice change request received, applying new voice configuration...",
                    "is_system_message": True
                }))

                # If we have an active session, close it properly
                if connection_id in active_sessions and active_sessions[connection_id].get("session"):
                    try:
                        print(f"Closing existing session for connection {connection_id} to change voice")
                        # We don't need to actually close anything since we'll create a new session
                    except Exception as e:
                        await error_handler.handle_session_close_error(e)

                # Remove from active sessions to prepare for new session
                if connection_id in active_sessions:
                    del active_sessions[connection_id]
                    print(f"Removed connection {connection_id} from active sessions for voice change")
            except asyncio.TimeoutError:
                await error_handler.handle_voice_config_timeout()
                return
            except Exception as e:
                await error_handler.handle_voice_change_error(e)
                return

        # Extract voice and model configuration
        client_config = extract_voice_and_model_configuration(config_data)
        voice_name = client_config["voice_name"]
        model_name = client_config["model_name"]
        allow_model_override = client_config["allow_override"]
        instructions = config_data.get("instructions", "")

        # Additional server-side validation
        from main_server_files.api_configuration.gemini_config import validate_model, ALLOW_CLIENT_MODEL_OVERRIDE, MODEL_VALIDATION_ENABLED, get_allowed_models_list

        if MODEL_VALIDATION_ENABLED:
            if allow_model_override and not ALLOW_CLIENT_MODEL_OVERRIDE:
                await error_handler.handle_model_validation_error(
                    f"Client requested model override but server has disabled model override functionality"
                )
                return
            elif allow_model_override and not validate_model(model_name, allow_override=True):
                await error_handler.handle_model_validation_error(
                    f"Client requested invalid model '{model_name}'. Allowed models: {get_allowed_models_list()}"
                )
                return

        # Load chat history
        chat_history = load_chat_history()

        # Build context from chat history
        context = []
        for msg in chat_history[-10:]:  # Use last 10 messages for context
            context.append({
                "role": "user" if msg['role'] == 'user' else "model",
                "parts": [{"text": msg['content']}]
            })

        # Create configuration with context and instructions if available
        config = create_gemini_config(voice_name=voice_name, instructions=instructions)
        print(f"Created configuration with voice: {voice_name} and instructions: {bool(instructions)}")

        # Send a message to the client that we're connecting to Gemini
        await connection_monitor.safe_send(json.dumps({
            "text": "Connecting to Gemini API...",
            "is_system_message": True
        }))

        try:
            # Fix the connection handling to properly use the async context manager
            print(f"Connecting to Gemini API for connection: {connection_id}")

            # Configuration already created above with instructions
            print(f"Using configuration with voice: {voice_name} and instructions: {bool(instructions)}")

            # Create client with correct API version for the model.
            # The client may supply its own key via the settings panel; it wins
            # over the server-side key when it looks valid.
            from main_server_files.api_configuration.api_client_manager import initialize_api_client
            session_client = initialize_api_client(model_name, client_key=config_data.get("apiKey"))

            # Update the audio processor with the client
            audio_processor.client = session_client

            # Connect to Gemini API using the proper async context manager pattern
            async with session_client.aio.live.connect(model=model_name, config=config) as session:
                print(f"Connected to Gemini API with voice: {voice_name} using model: {model_name}")

                # Instructions are now included in the system_instruction config, no need to send separately
                if instructions and instructions.strip():
                    print(f"System instructions configured in session: {instructions[:100]}...")

                # Add to active sessions
                active_sessions[connection_id] = {
                    "session": session,
                    "voice_name": voice_name,
                    "connected_at": datetime.datetime.now().isoformat(),
                    "client": session_client  # Store the client instance
                }
                print(f"Active sessions: {len(active_sessions)}")

                # Notify the client that we're connected
                await connection_monitor.safe_send(json.dumps({
                    "text": "Connected to Gemini API - ready for text input",
                    "is_system_message": True
                }))

                # Send connection stability warning
                await connection_monitor.safe_send(json.dumps({
                    "text": "IMPORTANT: Keep this connection open to send text messages. The session will remain active.",
                    "is_system_message": True,
                    "connection_guidance": True
                }))

                # Initialize audio processor with sequential preference
                audio_processor.is_sequential = config_data.get("sequentialAudioPlay", False)
                print(f"Sequential audio playback {'enabled' if audio_processor.is_sequential else 'disabled'} for connection {connection_id}")

                # Set up keep-alive ping using the new component
                keep_alive_manager = KeepAliveManager(websocket, connection_id, connection_monitor)
                await keep_alive_manager.start_keep_alive()  # We don't need to store the task reference anymore

                # Start the audio queue processor with error recovery
                audio_queue_task = asyncio.create_task(audio_processor.process_audio_queue())

                # Add connection recovery monitoring
                connection_recovery_task = asyncio.create_task(
                    connection_monitor.monitor_connection_recovery()
                )

                # Start tasks for sending and receiving messages
                send_task = asyncio.create_task(send_to_gemini(session, websocket, connection_monitor, connection_id, audio_processor, session_client))
                receive_task = asyncio.create_task(receive_from_gemini(
                    session=session,
                    websocket=websocket,
                    connection_monitor=connection_monitor,
                    connection_id=connection_id,
                    audio_processor=audio_processor,
                    voice_name=voice_name,
                    client=session_client,
                    initialize_gemini_session=initialize_gemini_session
                ))

                try:
                    # Wait for all tasks to complete with connection recovery
                    done, pending = await asyncio.wait(
                        [send_task, receive_task, monitor_task, connection_recovery_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    # Check for exceptions
                    for task in done:
                        if task.exception():
                            print(f"Task failed with exception for connection {connection_id}: {task.exception()}")
                            # Cancel other tasks
                            for p in pending:
                                p.cancel()
                            break
                except Exception as e:
                    await error_handler.handle_session_tasks_error(e, [send_task, receive_task, monitor_task, connection_recovery_task])
                finally:
                    # Stop and cancel keep-alive task when done
                    if 'keep_alive_manager' in locals():
                        keep_alive_manager.stop()

                    # Cancel audio queue task
                    audio_queue_task.cancel()

                    # Cancel any remaining tasks
                    if 'send_task' in locals() and not send_task.done():
                        send_task.cancel()
                    if 'receive_task' in locals() and not receive_task.done():
                        receive_task.cancel()
                    if 'monitor_task' in locals() and not monitor_task.done():
                        monitor_task.cancel()
                    if 'connection_recovery_task' in locals() and not connection_recovery_task.done():
                        connection_recovery_task.cancel()

                    await error_handler.send_session_closed_message()

        except Exception as e:
            # Use handle_session_error instead of handle_gemini_connection_error
            await error_handler.handle_session_error(e)
            return

    except asyncio.TimeoutError:
        await error_handler.handle_timeout_error()
    except websockets.exceptions.ConnectionClosed as e:
        await error_handler.handle_connection_closed(e)
    except Exception as e:
        await error_handler.handle_session_error(e)
    finally:
        # Log session duration for diagnostics
        session_duration = time.time() - session_start_time
        print(f"Session {connection_id} ended after {session_duration:.1f} seconds")

        if session_duration < 60:
            print(f"WARNING: Session {connection_id} was very short ({session_duration:.1f}s). Check frontend connection handling.")

        # Always clean up resources
        if has_semaphore:
            # Release the semaphore if it was acquired
            session_semaphore.release()
            semaphore_acquired.discard(connection_id)
            print(f"Released semaphore for connection {connection_id}")
        await cleanup_resources(connection_id)
        print(f"Connection {connection_id} handler completed")
