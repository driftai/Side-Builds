import json
import asyncio
import websockets
import logging
from .response_handler import GeminiResponseHandler
from ..api_configuration.gemini_config import MODEL, TimeoutConfig, usage_monitor
from ..chat_history.chat_history_handler import load_chat_history
from ..server_initialization.reconnection_handler import reconnect_to_gemini
from ..error_handling.api_error_handler import api_error_handler
from ..status_monitoring.api_usage_monitor import api_usage_tracker

# Configure logging for raw response data
logging.basicConfig(level=logging.INFO)
response_logger = logging.getLogger('gemini_responses')

async def _receive_responses(session, response_handler, connection_monitor, connection_id):
    """Helper function to handle receiving responses from Gemini session with enhanced error resilience and persistent session support"""
    
    try:
        async for response in session.receive():
            if response.server_content is None:
                print(f'Unhandled server message!')
                continue

            # Check if connection is still active before processing
            if not connection_monitor.is_websocket_open():
                print(f"Connection {connection_id} closed during response processing")
                break

            # Log raw response structure for debugging
            try:
                response_logger.debug(f"Raw response structure for {connection_id}: {response}")
                if hasattr(response, 'server_content') and response.server_content:
                    response_logger.debug(f"Server content attributes: {dir(response.server_content)}")
            except Exception as e:
                response_logger.warning(f"Could not log raw response: {e}")

            # Enhanced response parsing with defensive programming
            try:
                # Reset completion handling flag for each new response
                setattr(response_handler, '_completion_handled', False)

                # Check if response has server_content with defensive checks
                server_content = getattr(response, 'server_content', None)
                if server_content is None:
                    print(f"No server_content in response for connection {connection_id}")
                    continue

                # DEBUG: Log all server_content attributes for troubleshooting
                try:
                    server_attrs = [attr for attr in dir(server_content) if not attr.startswith('_')]
                    response_logger.debug(f"Server content attributes for {connection_id}: {server_attrs}")
                except Exception as e:
                    response_logger.warning(f"Could not log server content attributes: {e}")

                # Check for turn completion first (based on Live API documentation)
                turn_complete = getattr(server_content, 'turn_complete', None)
                if turn_complete is not None and turn_complete:
                    print(f"Turn complete detected via server_content.turn_complete for connection {connection_id}")
                    # Only handle completion if not already handled this response
                    if not getattr(response_handler, '_completion_handled', False):
                        setattr(response_handler, '_completion_handled', True)
                        await response_handler.handle_turn_complete()
                        # *** KEY FIX: Do NOT break or return here - just continue listening for next responses ***
                        # This allows the session to persist for multiple conversation turns
                        print(f"Turn completed for connection {connection_id}, session remaining active for next user input")
                    continue

                # Process model_turn content if available with enhanced error handling
                model_turn = getattr(server_content, 'model_turn', None)
                if model_turn is not None:
                    # Process response parts if they exist
                    parts = getattr(model_turn, 'parts', None)
                    if parts:
                        for part in parts:
                            await response_handler.process_response_part(part)
                    else:
                        print(f"No parts found in model_turn for connection {connection_id}")
                        # Don't continue here - let the code fall through to check other completion indicators
                else:
                    # Enhanced handling for missing model_turn - this is common and shouldn't break the connection
                    response_logger.info(f"No model_turn in server_content for connection {connection_id} - checking for other completion indicators")

                    # Check if we have any audio data that needs to be sent
                    try:
                        # Check for any pending audio chunks that should be sent to client
                        audio_chunks = getattr(server_content, 'audio_chunks', None)
                        if audio_chunks:
                            response_logger.info(f"Found {len(audio_chunks)} audio chunks in server_content without model_turn")
                            # Process audio chunks directly if available
                            for chunk in audio_chunks:
                                if hasattr(chunk, 'data') and chunk.data:
                                    await response_handler.process_audio_chunk(chunk.data)
                        else:
                            # Check for inline audio data in server_content
                            inline_data = getattr(server_content, 'inline_data', None)
                            if inline_data:
                                response_logger.info(f"Found inline_data in server_content without model_turn")
                                await response_handler.process_audio_chunk(inline_data)

                        # Check for completion indicators in server_content directly
                        server_turn_complete = getattr(server_content, 'turn_complete', None)
                        if server_turn_complete:
                            response_logger.info(f"Turn complete detected in server_content for connection {connection_id}")
                            # Only handle completion if not already handled this response
                            if not getattr(response_handler, '_completion_handled', False):
                                setattr(response_handler, '_completion_handled', True)
                                await response_handler.handle_turn_complete()
                            continue

                    except Exception as e:
                        response_logger.warning(f"Error processing server_content without model_turn: {e}")

                    # Don't break the connection - continue to check other completion indicators below

                # Check for completion indicators in server_content directly when model_turn is missing
                if not model_turn:
                    # Check for completion indicators in server_content when model_turn is None
                    server_turn_complete = getattr(server_content, 'turn_complete', None)
                    server_final = getattr(server_content, 'final', None)
                    server_finished = getattr(server_content, 'finished', None)
                    server_complete = getattr(server_content, 'complete', None)

                    # If any completion indicator is found, handle turn completion
                    if server_turn_complete or server_final or server_finished or server_complete:
                        print(f"Turn complete detected in server_content (turn_complete={server_turn_complete}, final={server_final}, finished={server_finished}, complete={server_complete})")
                        # Only handle completion if not already handled this response
                        if not getattr(response_handler, '_completion_handled', False):
                            setattr(response_handler, '_completion_handled', True)
                            await response_handler.handle_turn_complete()
                        continue

                    # FORCE COMPLETION: If no completion indicators are found but we have audio data,
                    # first try to inject completion indicators, then force completion if needed
                    try:
                        # Try to inject completion indicators first
                        injected = await response_handler.inject_completion_indicator(server_content)
                        if injected:
                            response_logger.info(f"Successfully injected completion indicator for connection {connection_id}")
                            # Since we injected the indicator, it will be detected in the next iteration
                            continue

                        # If injection failed, check if we have accumulated audio data that should trigger completion.
                        # Same audible floor as the fallback below: a priming frame is not a turn.
                        audio_size = len(getattr(response_handler.audio_processor, 'audio_data', []))
                        if audio_size >= response_handler.MIN_MEANINGFUL_AUDIO_BYTES:
                            # Force completion if we have audio data and no completion indicators
                            response_logger.info(f"Forcing turn completion for connection {connection_id} - audio_size: {audio_size} bytes")
                            # Only handle completion if not already handled this response
                            if not getattr(response_handler, '_completion_handled', False):
                                setattr(response_handler, '_completion_handled', True)
                                await response_handler.handle_turn_complete()
                            continue
                        else:
                            # No audio data and no completion indicators - this might be an empty response
                            response_logger.debug(f"No audio data and no completion indicators for connection {connection_id}")
                    except Exception as e:
                        response_logger.warning(f"Error in completion indicator injection/checking: {e}")

                # Fallback: Check for legacy completion indicators (only if model_turn exists)
                elif model_turn:
                    final_attr = getattr(model_turn, 'final', None)
                    if final_attr is not None and final_attr:
                        # Only handle completion if not already handled this response
                        if not getattr(response_handler, '_completion_handled', False):
                            setattr(response_handler, '_completion_handled', True)
                            await response_handler.handle_turn_complete()
                            print("Turn complete (legacy final=True), session remaining active")
                        continue

                    # Fallback: Check for other completion indicators
                    is_finished = getattr(model_turn, 'finished', None)
                    is_complete = getattr(model_turn, 'complete', None)

                    if is_finished or is_complete:
                        # Only handle completion if not already handled this response
                        if not getattr(response_handler, '_completion_handled', False):
                            setattr(response_handler, '_completion_handled', True)
                            await response_handler.handle_turn_complete()
                            print(f"Turn complete (finished={is_finished}, complete={is_complete}), session remaining active")
                        continue

                # Final fallback: Check for audio completion based on timing and content
                try:
                    completed = await response_handler.check_audio_completion()
                    if completed:
                        print(f"Audio completion detected via timing for connection {connection_id}")
                        continue
                except Exception as e:
                    response_logger.warning(f"Error in audio completion check: {e}")

                # ABSOLUTE FINAL FALLBACK: If nothing else works, inject completion indicator or force completion
                # This prevents the connection from hanging indefinitely.
                #
                # Only ever fire once the turn has actually produced audio. This used
                # to run on any unrecognised frame, so a model whose first
                # server_content carries no model_turn - gemini-3.1-flash-live-preview
                # does exactly that - had its turn declared complete with 0 bytes
                # before generation began. The client got the end-of-turn sentinel
                # with no audio, and the real audio arrived ~200ms later with nowhere
                # to go. A turn that has generated nothing yet is not a hung turn,
                # it just has not started; keep listening.
                pending_audio = len(getattr(response_handler.audio_processor, 'audio_data', b'') or b'')
                if pending_audio < response_handler.MIN_MEANINGFUL_AUDIO_BYTES:
                    response_logger.debug(
                        f"Unrecognised frame with only {pending_audio} bytes for connection {connection_id} - "
                        "waiting for generation rather than forcing completion"
                    )
                    continue

                response_logger.info(f"Applying absolute fallback completion for connection {connection_id}")
                try:
                    # First try to inject completion indicator
                    injected = await response_handler.inject_completion_indicator(server_content)
                    if injected:
                        response_logger.info(f"Absolute fallback: injected completion indicator for connection {connection_id}")
                        continue
                    else:
                        # If injection fails, force completion directly
                        # Only handle completion if not already handled this response
                        if not getattr(response_handler, '_completion_handled', False):
                            setattr(response_handler, '_completion_handled', True)
                            await response_handler.handle_turn_complete()
                            print(f"Absolute fallback completion forced for connection {connection_id}")
                        continue
                except Exception as e:
                    response_logger.error(f"Critical error in absolute fallback completion: {e}")
                    # If even the fallback fails, we need to continue the loop to prevent hanging
                    continue
                                
            except AttributeError as e:
                print(f"AttributeError in response parsing for connection {connection_id}: {e}")
                response_logger.warning(f"Response structure error for {connection_id}: {e}")
                # Defensive fallback: try to complete any pending audio
                try:
                    await response_handler.check_audio_completion()
                except Exception as fallback_error:
                    print(f"Fallback audio completion failed: {fallback_error}")
            except Exception as e:
                print(f"Unexpected error in response parsing for connection {connection_id}: {e}")
                response_logger.error(f"Response parsing error for {connection_id}: {e}")
                # Try to handle any pending audio before continuing
                try:
                    await response_handler.check_audio_completion()
                except Exception as fallback_error:
                    print(f"Fallback audio completion failed: {fallback_error}")
                
    except websockets.exceptions.ConnectionClosedOK:
        # This is a normal connection closure (code 1000), not an error
        print(f"Connection {connection_id} closed normally during response receiving")
    except websockets.exceptions.ConnectionClosed as e:
        # Handle deadline errors and other connection closures through the API error handler
        error_msg = str(e)
        print(f"Connection {connection_id} closed during response receiving: {e}")
        
        # Track this as an error in usage monitoring
        usage_monitor.increment_error()
        
        # Check if this is a deadline error and handle it properly
        if "deadline expired before operation could complete" in error_msg.lower() or e.code == 1011:
            # Track deadline errors specifically
            usage_monitor.increment_deadline_error()
            # This is a deadline error - raise it so the outer handler can process it through the API error handler
            raise Exception(f"Deadline expired error: {error_msg}")
        else:
            # For other connection closures, just re-raise
            raise
    except asyncio.CancelledError:
        print(f"Response receiving task cancelled for connection {connection_id}")
        raise  # Re-raise so the task is properly cancelled
    except Exception as e:
        print(f"Error in _receive_responses for connection {connection_id}: {e}")
        usage_monitor.increment_error()
        
        # Send error message to client if possible
        if connection_monitor.is_websocket_open():
            await connection_monitor.safe_send(json.dumps({
                "text": f"Error receiving response: {str(e)}",
                "is_system_message": True,
                "is_error": True
            }))
        # Re-raise the exception so it can be handled by the outer error handler
        raise

async def receive_from_gemini(session, websocket, connection_monitor, connection_id, audio_processor, voice_name, client=None, initialize_gemini_session=None):
    """Receive and process responses from Gemini with enhanced timeout management, error handling, and persistent session support."""
    response_handler = GeminiResponseHandler(connection_monitor, audio_processor)
    receive_task = None
    consecutive_errors = 0
    deadline_consecutive_errors = 0
    max_consecutive_errors = 5
    max_deadline_errors = TimeoutConfig.MAX_CONSECUTIVE_DEADLINE_ERRORS
    retry_attempt = 0
    
    # Track this request in the API usage monitor
    request_index = api_usage_tracker.log_request_start(str(connection_id), "chat_response")
    request_start_time = asyncio.get_event_loop().time()
    
    try:
        # *** KEY FIX: Keep session alive for multiple conversation turns ***
        print(f"Starting persistent response handler for connection {connection_id}")
        
        while True:
            if not connection_monitor.is_websocket_open():
                print(f"Connection {connection_id} closed, stopping response handler")
                break

            try:
                print(f"Waiting for Gemini response (attempt {retry_attempt + 1})...")
                usage_monitor.increment_request()
                
                # Use configurable timeout based on retry attempt
                current_timeout = TimeoutConfig.get_response_timeout(retry_attempt)
                
                # Create task for receiving responses with dynamic timeout.
                #
                # NOTE: a connection health check used to race in this wait() as a
                # third task. A ping to a browser on localhost resolves in ~1ms, so
                # it won the FIRST_COMPLETED race almost every time, cancelled both
                # real tasks below, matched neither completion branch, and dropped
                # straight back into `while True` with no backoff - a hot spin that
                # tore down and rebuilt the Gemini receive task thousands of times a
                # second. Liveness is still covered: ConnectionMonitor.monitor_connection()
                # pings on its own cadence, is_websocket_open() gates the top of this
                # loop, and the timeout branch below pings before deciding to retry.
                timeout_task = asyncio.create_task(asyncio.sleep(current_timeout))
                receive_task = asyncio.create_task(_receive_responses(session, response_handler, connection_monitor, connection_id))

                done, pending = await asyncio.wait([timeout_task, receive_task], return_when=asyncio.FIRST_COMPLETED)

                # Cancel any pending tasks
                for task in pending:
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass  # Expected when cancelling
                        except Exception as e:
                            print(f"Error during task cancellation: {e}")

                # Check what completed
                if timeout_task in done:
                    print(f"Timeout waiting for Gemini response after {current_timeout} seconds")

                    # Nothing arrived for the whole timeout window - now a health
                    # check is actually informative, so run it here instead of
                    # racing it against the work.
                    try:
                        if not await connection_monitor.ping_connection():
                            print(f"Connection health check failed for {connection_id}, stopping response handler")
                            break
                    except Exception as e:
                        print(f"Error checking connection health: {e}")

                    # Log timeout in API usage tracker
                    api_usage_tracker.log_timeout(str(connection_id), current_timeout)
                    
                    # Check if we have accumulated audio data that needs processing
                    if hasattr(audio_processor, 'audio_data') and len(audio_processor.audio_data) > 0:
                        print(f"Processing accumulated audio data on timeout: {len(audio_processor.audio_data)} bytes")
                        try:
                            await response_handler.handle_turn_complete()
                        except Exception as e:
                            print(f"Error processing accumulated audio on timeout: {e}")
                    
                    # Reset consecutive errors on timeout (not an error) but increment retry attempt
                    consecutive_errors = 0
                    deadline_consecutive_errors = 0
                    retry_attempt = min(retry_attempt + 1, 3)  # Cap retry attempts
                    
                    # *** KEY FIX: Continue waiting for next user input instead of breaking ***
                    print(f"Timeout handled, continuing to listen for next user input on connection {connection_id}")
                    continue
                elif receive_task in done:
                    # Check if the task completed with an exception
                    try:
                        await receive_task  # This will raise any exception that occurred
                        print(f"Response receiving completed normally for connection {connection_id}")
                        # Reset all error counters on successful completion
                        consecutive_errors = 0
                        deadline_consecutive_errors = 0
                        retry_attempt = 0
                        
                        # *** KEY FIX: Continue listening for next conversation turn instead of breaking ***
                        print(f"Turn completed successfully, continuing session for connection {connection_id}")
                        continue
                    except websockets.exceptions.ConnectionClosedOK:
                        print(f"Connection {connection_id} closed normally, stopping response handler")
                        break
                    except websockets.exceptions.ConnectionClosed as e:
                        print(f"Connection {connection_id} closed: {e}")
                        
                        # Handle deadline errors through API error handler
                        error_msg = str(e)
                        if "deadline expired before operation could complete" in error_msg.lower() or e.code == 1011:
                            deadline_consecutive_errors += 1
                            consecutive_errors += 1
                            print(f"Deadline error detected (deadline: {deadline_consecutive_errors}/{max_deadline_errors}, total: {consecutive_errors}/{max_consecutive_errors})")
                            
                            # Log deadline error in API usage tracker
                            api_usage_tracker.log_error(str(connection_id), "deadline_error", error_msg, is_deadline_error=True)
                            
                            # Use enhanced error handler for deadline errors
                            deadline_error = Exception(f"Deadline expired error: {error_msg}")
                            should_retry, handler_msg = await api_error_handler.handle_api_error(deadline_error, connection_id, MODEL)
                            
                            if should_retry and deadline_consecutive_errors < max_deadline_errors and consecutive_errors < max_consecutive_errors:
                                print(f"API Error Handler: {handler_msg}")
                                if connection_monitor.is_websocket_open():
                                    await connection_monitor.safe_send(json.dumps({
                                        "text": f"Backend experiencing delays (attempt {deadline_consecutive_errors}/{max_deadline_errors}): {handler_msg}",
                                        "is_system_message": True
                                    }))
                                retry_attempt += 1
                                continue  # Try again
                            else:
                                print(f"Too many consecutive deadline errors ({deadline_consecutive_errors}) or handler recommends stopping: {handler_msg}")
                                if connection_monitor.is_websocket_open():
                                    await connection_monitor.safe_send(json.dumps({
                                        "text": f"Backend connection unstable: {handler_msg}. Stopping attempts to prevent overload.",
                                        "is_system_message": True,
                                        "is_error": True
                                    }))
                                break
                        else:
                            # For other connection closures, just break
                            break
                    except asyncio.CancelledError:
                        print(f"Response receiving task cancelled for connection {connection_id}")
                        break
                    except Exception as e:
                        consecutive_errors += 1
                        print(f"Error in response receiving task (consecutive: {consecutive_errors}/{max_consecutive_errors}): {e}")
                        
                        # Log error in API usage tracker
                        api_usage_tracker.log_error(str(connection_id), "response_error", str(e), is_deadline_error=False)
                        
                        # Use enhanced error handler for all other errors
                        should_retry, error_msg = await api_error_handler.handle_api_error(e, connection_id, MODEL)
                        
                        if should_retry and consecutive_errors < max_consecutive_errors:
                            print(f"API Error Handler: {error_msg}")
                            if connection_monitor.is_websocket_open():
                                await connection_monitor.safe_send(json.dumps({
                                    "text": f"Retrying after error (attempt {consecutive_errors}/{max_consecutive_errors}): {error_msg}",
                                    "is_system_message": True
                                }))
                            retry_attempt += 1
                            continue
                        else:
                            print(f"Too many consecutive errors ({consecutive_errors}) or handler recommends stopping: {error_msg}")
                            if connection_monitor.is_websocket_open():
                                await connection_monitor.safe_send(json.dumps({
                                    "text": f"Connection error (stopping after {consecutive_errors} attempts): {error_msg}",
                                    "is_system_message": True,
                                    "is_error": True
                                }))
                            break
                        
            except Exception as e:
                consecutive_errors += 1
                print(f"Error in receive_from_gemini loop (consecutive: {consecutive_errors}/{max_consecutive_errors}): {e}")
                
                # Log error in API usage tracker
                api_usage_tracker.log_error(str(connection_id), "connection_error", str(e), is_deadline_error=False)
                
                # Use enhanced error handler to determine if we should retry
                should_retry, error_msg = await api_error_handler.handle_api_error(e, connection_id, MODEL)
                
                if should_retry and consecutive_errors < max_consecutive_errors:
                    print(f"API Error Handler: {error_msg}")
                    if connection_monitor.is_websocket_open():
                        await connection_monitor.safe_send(json.dumps({
                            "text": f"Retrying connection (attempt {consecutive_errors}/{max_consecutive_errors}): {error_msg}",
                            "is_system_message": True
                        }))
                    retry_attempt += 1
                    continue
                else:
                    print(f"Stopping due to too many errors ({consecutive_errors}) or handler recommendation: {error_msg}")
                    if connection_monitor.is_websocket_open():
                        await connection_monitor.safe_send(json.dumps({
                            "text": f"Connection failed after {consecutive_errors} attempts: {error_msg}",
                            "is_system_message": True,
                            "is_error": True
                        }))
                    break
    
    except Exception as e:
        print(f"Critical error in receive_from_gemini: {e}")
        if connection_monitor.is_websocket_open():
            await connection_monitor.safe_send(json.dumps({
                "text": f"Critical connection error: {str(e)}",
                "is_system_message": True,
                "is_error": True
            }))
    finally:
        # Log final usage statistics
        stats = usage_monitor.get_stats()
        print(f"\nConnection {connection_id} usage statistics:")
        print(f"  Requests: {stats['requests']}")
        print(f"  Errors: {stats['errors']} (rate: {stats['error_rate']:.2%})")
        print(f"  Deadline errors: {stats['deadline_errors']} (rate: {stats['deadline_error_rate']:.2%})")
        
        # Track request completion in API usage monitor
        if 'request_start_time' in locals():
            response_time = asyncio.get_event_loop().time() - request_start_time
            success = consecutive_errors == 0 and deadline_consecutive_errors == 0
            api_usage_tracker.log_request_completion(request_index, success, response_time)
        
        # Cancel any remaining tasks
        if receive_task and not receive_task.done():
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"Error during final task cleanup: {e}")
        
        print(f"Persistent response handler for connection {connection_id} terminated") 