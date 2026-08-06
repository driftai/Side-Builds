import json
import asyncio
import websockets
import traceback
import time
from ..chat_history.chat_history_handler import load_chat_history
from ..api_configuration.gemini_config import MAIN_MODEL as MODEL
from ..media_processing.realtime_input_processor import process_realtime_input
from ..command_processing import process_command
from ..session_management.gemini_session_initializer import initialize_gemini_session

async def send_to_gemini(session, websocket, connection_monitor, connection_id, audio_processor, client=None):
    """Sends messages from the client websocket to the Gemini API.
    
    Args:
        session: The Gemini API session
        websocket: The websocket connection
        connection_monitor: The connection monitor instance
        connection_id: The unique connection ID
        audio_processor: The audio processor instance
        client: The Gemini API client instance (needed for reinitialization)
    """
    retry_count = 0
    max_retries = 3
    
    while retry_count < max_retries:
        try:
            while True:  # Add outer loop for reinitialization
                print(f"Starting WebSocket message loop for connection {connection_id}")
                try:
                    async for message in websocket:
                        try:
                            # Record activity for any message received from the client
                            connection_monitor.record_activity()
                            data = json.loads(message)
                            print(f"Received message from client {connection_id}: {data.get('type', 'unknown type')}")
                            
                            # *** ENHANCED MESSAGE TYPE ROUTING SYSTEM ***
                            # Implement intelligent message classification to handle all message types gracefully
                            
                            # *** SETUP & CONFIGURATION MESSAGES ***
                            if "setup" in data:
                                # Client setup/configuration messages - these are initialization messages
                                print("Received client setup configuration message")
                                # Extract model and voice configuration from setup message for reading section
                                setup_data = data.get("setup", {})
                                if setup_data:
                                    model_name = setup_data.get("model", "gemini-2.0-flash-live-001")
                                    voice_name = None
                                    # Try to extract voice from speechConfig
                                    speech_config = setup_data.get("speechConfig", {})
                                    if speech_config:
                                        voice_config = speech_config.get("voiceConfig", {})
                                        if voice_config:
                                            prebuilt_config = voice_config.get("prebuiltVoiceConfig", {})
                                            if prebuilt_config:
                                                voice_name = prebuilt_config.get("voiceName")

                                    print(f"Extracted from setup - Model: {model_name}, Voice: {voice_name}")

                                    # Update active session info if available
                                    if connection_id in active_sessions:
                                        active_sessions[connection_id]["model"] = model_name
                                        if voice_name:
                                            active_sessions[connection_id]["voice_name"] = voice_name

                                # Send acknowledgment
                                try:
                                    setup_ack = {
                                        "type": "setup_acknowledgment",
                                        "message": "Setup configuration received",
                                        "timestamp": time.time()
                                    }
                                    await connection_monitor.safe_send(json.dumps(setup_ack))
                                except Exception as ack_error:
                                    print(f"Warning: Could not send setup acknowledgment: {ack_error}")
                                continue
                            
                            # *** TYPED MESSAGE HANDLING ***
                            elif "type" in data:
                                message_type = data.get("type")
                                
                                # *** COMPREHENSIVE PING/PONG HANDLING ***
                                if message_type in ["application_ping", "ping", "keepalive", "heartbeat"]:
                                    print(f"Received {message_type} from client, sending pong response")
                                    # *** RESTORED APPLICATION-LEVEL PING HANDLER ***
                                    pong_response = {
                                        "type": "application_pong",
                                        "message": "pong",
                                        "timestamp": data.get("timestamp"),
                                        "server_timestamp": time.time(),
                                        "client_id": connection_id
                                    }
                                    await connection_monitor.safe_send(json.dumps(pong_response))
                                    continue
                                    
                                # *** EXPLICIT DISCONNECT ***
                                elif message_type == "disconnect":
                                    # Close the Gemini session on purpose rather than
                                    # letting it fall out of a cancelled task.
                                    #
                                    # Dropping the client socket does end the session,
                                    # but it unwinds through cancellation, so the
                                    # connection to Google is torn down rather than
                                    # closed - and the service can hold the session
                                    # slot for that key until its own timeout. Asking
                                    # the session to close first releases it now,
                                    # which is the point of the button: freeing the
                                    # API for something else to use.
                                    print(f"Client {connection_id} asked to disconnect; closing Gemini session")
                                    try:
                                        # The live session this loop is already
                                        # serving - no lookup needed, and the
                                        # module-level table is not imported here.
                                        if session is not None and hasattr(session, "close"):
                                            await session.close()
                                            print(f"Gemini session closed cleanly for {connection_id}")
                                    except Exception as close_error:
                                        print(f"Could not close Gemini session cleanly: {close_error}")
                                    # Ending the read loop unwinds the handler normally.
                                    return

                                # *** COMMAND MESSAGE HANDLING ***
                                elif message_type in ["command", "action", "request"]:
                                    print(f"Processing typed command: {data.get('command', data.get('action', 'unknown'))}")
                                    await process_command(data, connection_monitor, audio_processor, connection_id)
                                    continue
                                    
                                # *** STATUS AND MONITORING MESSAGES ***
                                elif message_type in ["status_update", "client_status", "connection_test"]:
                                    print(f"Received client status message: {message_type}")
                                    # Send status acknowledgment
                                    status_response = {
                                        "type": "status_acknowledgment",
                                        "received_type": message_type,
                                        "server_status": "active",
                                        "timestamp": time.time()
                                    }
                                    await connection_monitor.safe_send(json.dumps(status_response))
                                    continue
                                    
                                # *** CONFIGURATION MESSAGES ***
                                elif message_type in ["config", "settings", "preferences"]:
                                    print(f"Received configuration message: {message_type}")
                                    # Handle configuration updates
                                    await process_command(data, connection_monitor, audio_processor, connection_id)
                                    continue
                                    
                                else:
                                    print(f"Received typed message with unrecognized type: {message_type}")
                                    # Try to process as command anyway as fallback
                                    try:
                                        await process_command(data, connection_monitor, audio_processor, connection_id)
                                    except Exception as fallback_error:
                                        print(f"Fallback processing failed for typed message: {fallback_error}")
                                    continue
                            
                            # *** REALTIME INPUT PROCESSING ***
                            elif "realtime_input" in data:
                                # This is genuine realtime input data for the AI model
                                await process_realtime_input(data, session, connection_monitor, audio_processor)
                                continue
                            
                            # *** LEGACY COMMAND PROCESSING ***
                            elif any(key in data for key in ["command", "clear_history", "voice_change", "get_history", "new_model", "action"]):
                                # Legacy command format - maintain backward compatibility
                                print(f"Processing legacy command: {data.get('command', data.get('action', 'legacy_command'))}")
                                await process_command(data, connection_monitor, audio_processor, connection_id)
                                continue
                            
                            # *** LEGACY PING HANDLING FOR BACKWARD COMPATIBILITY ***
                            elif data.get("ping") == True or data.get("ping") == "ping":
                                print("Received legacy ping format from client, sending pong")
                                await connection_monitor.safe_send(json.dumps({
                                    "pong": True,
                                    "timestamp": time.time(),
                                    "server_time": time.time()
                                }))
                                continue
                            
                            # *** SILENT TIME & STATUS UPDATES ***
                            elif data.get("is_time_update") and data.get("is_silent_update"):
                                # Silent time updates don't need processing or logging
                                continue
                            elif data.get("is_silent_update") or data.get("silent"):
                                # Other silent updates
                                continue
                            
                            # *** CHAT HISTORY AND CONTEXT MESSAGES ***
                            elif any(key in data for key in ["history", "context", "conversation_history", "chat_context"]):
                                print("Received chat history/context message")
                                await process_command(data, connection_monitor, audio_processor, connection_id)
                                continue
                            
                            # *** MEDIA AND MULTIMODAL MESSAGES ***
                            elif any(key in data for key in ["media", "audio", "video", "image", "file"]):
                                print("Received media/multimodal message")
                                # Route to appropriate media processing
                                try:
                                    await process_realtime_input(data, session, connection_monitor, audio_processor)
                                except Exception as media_error:
                                    print(f"Media processing failed, trying command processing: {media_error}")
                                    await process_command(data, connection_monitor, audio_processor, connection_id)
                                continue
                            
                            # *** ENHANCED WARNING FOR TRULY UNKNOWN MESSAGES ***
                            else:
                                # Only warn about genuinely unrecognized message structures
                                message_keys = sorted(list(data.keys()))  # Sort for consistent logging
                                message_size = len(str(data))
                                
                                # Check if this looks like a data message we should process anyway
                                if len(message_keys) > 0 and message_size > 10:
                                    print(f"INFO: Processing unrecognized message structure with keys: {message_keys}")
                                    # Preview first part of message for debugging (but limit size)
                                    message_preview = str(data)[:100] + ("..." if len(str(data)) > 100 else "")
                                    print(f"Message preview: {message_preview}")
                                    
                                    # Try to process as command with enhanced error handling
                                    try:
                                        await process_command(data, connection_monitor, audio_processor, connection_id)
                                        print("Successfully processed unrecognized message as command")
                                    except Exception as unknown_error:
                                        print(f"Could not process unrecognized message: {unknown_error}")
                                        # Send error response to client
                                        error_response = {
                                            "type": "processing_error",
                                            "message": "Message format not recognized",
                                            "received_keys": message_keys,
                                            "timestamp": time.time()
                                        }
                                        await connection_monitor.safe_send(json.dumps(error_response))
                                else:
                                    # Very small or empty messages - likely malformed
                                    print(f"WARNING: Received malformed or empty message: {data}")

                        except json.JSONDecodeError as e:
                            print(f"ERROR: Failed to decode client message: {e}. Raw message: {message[:500]}...")
                            # Send JSON error response to client
                            try:
                                error_response = {
                                    "type": "json_error",
                                    "message": "Invalid JSON format",
                                    "error": str(e),
                                    "timestamp": time.time()
                                }
                                await connection_monitor.safe_send(json.dumps(error_response))
                            except Exception as error_send_error:
                                print(f"Could not send JSON error response: {error_send_error}")
                            
                        except Exception as e:
                            print(f"ERROR: Unhandled exception in message processing loop: {e}")
                            traceback.print_exc()
                            
                            # Send general error response to client
                            try:
                                error_response = {
                                    "type": "processing_error",
                                    "message": "Internal processing error",
                                    "error": str(e),
                                    "timestamp": time.time()
                                }
                                await connection_monitor.safe_send(json.dumps(error_response))
                            except Exception as error_send_error:
                                print(f"Could not send error response: {error_send_error}")
                            
                            await asyncio.sleep(1)  # Brief pause to prevent overwhelming on repeated errors
                    
                    # When the message loop ends naturally, try to reinitialize
                    print("WebSocket message loop finished gracefully. Attempting to reinitialize model...")
                    
                    # Check if the connection is still open before attempting reinitialization
                    if websocket.state in (websockets.protocol.State.CLOSED, websockets.protocol.State.CLOSING):
                        print("WebSocket is closed, cannot reinitialize")
                        return
                        
                    try:
                        # Build context from chat history
                        chat_history = load_chat_history()
                        context = []
                        for msg in chat_history[-10:]:  # Use last 10 messages for context
                            context.append({
                                "role": "user" if msg['role'] == 'user' else "model",
                                "parts": [{"text": msg['content']}]
                            })
                        
                        # Get the current voice name from active_sessions
                        voice_name = "Aoede"  # Default voice name
                        
                        # Try to reconnect to Gemini API
                        await connection_monitor.safe_send(json.dumps({
                            "text": "Reinitializing connection...",
                            "is_system_message": True
                        }))
                        
                        # Check if we have a client instance for reinitialization
                        if not client:
                            print("Error: No client instance available for reinitialization")
                            await connection_monitor.safe_send(json.dumps({
                                "text": "Failed to reinitialize: No client instance available",
                                "is_system_message": True,
                                "is_error": True
                            }))
                            return
                        
                        new_session = await initialize_gemini_session(
                            client=client,
                            voice_name=voice_name,
                            context=context,
                            websocket=websocket,
                            safe_send=connection_monitor.safe_send,
                            model=MODEL,
                            connection_id=connection_id
                        )
                        if new_session:
                            session = new_session
                            print("Successfully reinitialized model")
                            await connection_monitor.safe_send(json.dumps({
                                "text": "Connection reinitialized successfully",
                                "is_system_message": True
                            }))
                            # Reset retry count on successful reinitialization
                            retry_count = 0
                            continue
                        else:
                            print("Failed to reinitialize model")
                            await connection_monitor.safe_send(json.dumps({
                                "text": "Failed to reinitialize connection",
                                "is_system_message": True,
                                "is_error": True
                            }))
                    except Exception as e:
                        print(f"Error reinitializing model: {e}")
                        traceback.print_exc()
                        break  # Break the outer loop on error
                        
                except websockets.exceptions.ConnectionClosed as e:
                    print(f"Client connection {connection_id} closed: {e.code} - {e.reason}")
                    active_duration = time.time() - connection_monitor.last_activity_time
                    print(f"Connection was active for: {active_duration:.1f} seconds since last activity")

                    # Check if this is a premature closure (connection lasted less than expected)
                    if active_duration < 30:  # Less than 30 seconds
                        print(f"WARNING: Connection {connection_id} closed prematurely after only {active_duration:.1f} seconds!")
                        print("This suggests a frontend issue where the client is closing the connection too early.")
                        print("The Gemini session was established but the client disconnected before any user input.")
                        return
                    else:
                        print(f"Connection {connection_id} lasted {active_duration:.1f} seconds - may be normal closure")

                    # Check if this is a normal closure (code 1000) or an error
                    if e.code == 1000:
                        print(f"Normal connection closure for {connection_id}")
                        return
                    else:
                        print(f"Abnormal connection closure for {connection_id} (code {e.code}). This may indicate a client issue.")
                        return
                except Exception as e:
                    print(f"ERROR: Unhandled exception in outer message loop: {e}")
                    print(f"Exception occurred {time.time() - connection_monitor.last_activity_time:.1f} seconds after last activity")
                    traceback.print_exc()
                    break
                
        except Exception as e:
            print(f"ERROR: Unhandled exception in send_to_gemini task (retry loop level): {e}")
            traceback.print_exc()
            retry_count += 1
            if retry_count >= max_retries:
                print(f"ERROR: Failed after {max_retries} retries in send_to_gemini. Aborting task.")
                break
            else:
                print(f"Retrying send_to_gemini task (attempt {retry_count}/{max_retries})...")
                await asyncio.sleep(2 ** retry_count)
                
    print(f"send_to_gemini task ended for connection: {connection_id}") 