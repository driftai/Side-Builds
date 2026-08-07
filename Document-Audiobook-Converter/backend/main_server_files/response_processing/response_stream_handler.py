"""Gemini response receive supervision and stable public entry points."""

import asyncio
import json
import logging

import websockets

from .response_frame_processor import process_response_frame
from .response_handler import GeminiResponseHandler
from ..api_configuration.gemini_config import MODEL, TimeoutConfig, usage_monitor
from ..chat_history.chat_history_handler import load_chat_history
from ..server_initialization.reconnection_handler import reconnect_to_gemini
from ..error_handling.api_error_handler import api_error_handler
from ..status_monitoring.api_usage_monitor import api_usage_tracker


logging.basicConfig(level=logging.INFO)
response_logger = logging.getLogger('gemini_responses')


async def _receive_responses(
    session,
    response_handler,
    connection_monitor,
    connection_id,
):
    """Receive frames from one Gemini session and supervise frame failures."""
    try:
        async for response in session.receive():
            if response.server_content is None:
                print('Unhandled server message!')
                continue

            if not connection_monitor.is_websocket_open():
                print(
                    f"Connection {connection_id} closed during response processing"
                )
                break

            try:
                response_logger.debug(
                    f"Raw response structure for {connection_id}: {response}"
                )
                if (
                    hasattr(response, 'server_content')
                    and response.server_content
                ):
                    response_logger.debug(
                        "Server content attributes: "
                        f"{dir(response.server_content)}"
                    )
            except Exception as error:
                response_logger.warning(f"Could not log raw response: {error}")

            await process_response_frame(
                response,
                response_handler,
                connection_id,
                response_logger,
            )
    except websockets.exceptions.ConnectionClosedOK:
        print(
            f"Connection {connection_id} closed normally during response receiving"
        )
    except websockets.exceptions.ConnectionClosed as error:
        error_msg = str(error)
        print(
            f"Connection {connection_id} closed during response receiving: "
            f"{error}"
        )
        usage_monitor.increment_error()

        if (
            "deadline expired before operation could complete" in error_msg.lower()
            or error.code == 1011
        ):
            usage_monitor.increment_deadline_error()
            raise Exception(f"Deadline expired error: {error_msg}")
        raise
    except asyncio.CancelledError:
        print(f"Response receiving task cancelled for connection {connection_id}")
        raise
    except Exception as error:
        print(f"Error in _receive_responses for connection {connection_id}: {error}")
        usage_monitor.increment_error()

        if connection_monitor.is_websocket_open():
            await connection_monitor.safe_send(json.dumps({
                "text": f"Error receiving response: {str(error)}",
                "is_system_message": True,
                "is_error": True,
            }))
        raise


async def receive_from_gemini(
    session,
    websocket,
    connection_monitor,
    connection_id,
    audio_processor,
    voice_name,
    client=None,
    initialize_gemini_session=None,
):
    """Receive Gemini responses with persistent-session timeout supervision."""
    response_handler = GeminiResponseHandler(connection_monitor, audio_processor)
    receive_task = None
    consecutive_errors = 0
    deadline_consecutive_errors = 0
    max_consecutive_errors = 5
    max_deadline_errors = TimeoutConfig.MAX_CONSECUTIVE_DEADLINE_ERRORS
    retry_attempt = 0

    request_index = api_usage_tracker.log_request_start(
        str(connection_id), "chat_response"
    )
    request_start_time = asyncio.get_event_loop().time()

    try:
        print(f"Starting persistent response handler for connection {connection_id}")

        while True:
            if not connection_monitor.is_websocket_open():
                print(
                    f"Connection {connection_id} closed, stopping response handler"
                )
                break

            try:
                print(f"Waiting for Gemini response (attempt {retry_attempt + 1})...")
                usage_monitor.increment_request()

                current_timeout = TimeoutConfig.get_response_timeout(retry_attempt)

                # The connection monitor owns periodic health checks. Racing a
                # localhost ping here used to cancel real receive work in a hot loop.
                timeout_task = asyncio.create_task(asyncio.sleep(current_timeout))
                receive_task = asyncio.create_task(_receive_responses(
                    session,
                    response_handler,
                    connection_monitor,
                    connection_id,
                ))

                done, pending = await asyncio.wait(
                    [timeout_task, receive_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in pending:
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                        except Exception as error:
                            print(f"Error during task cancellation: {error}")

                if timeout_task in done:
                    print(
                        "Timeout waiting for Gemini response after "
                        f"{current_timeout} seconds"
                    )

                    try:
                        if not await connection_monitor.ping_connection():
                            print(
                                "Connection health check failed for "
                                f"{connection_id}, stopping response handler"
                            )
                            break
                    except Exception as error:
                        print(f"Error checking connection health: {error}")

                    api_usage_tracker.log_timeout(
                        str(connection_id), current_timeout
                    )

                    if (
                        hasattr(audio_processor, 'audio_data')
                        and len(audio_processor.audio_data) > 0
                    ):
                        print(
                            "Processing accumulated audio data on timeout: "
                            f"{len(audio_processor.audio_data)} bytes"
                        )
                        try:
                            await response_handler.handle_turn_complete()
                        except Exception as error:
                            print(
                                "Error processing accumulated audio on timeout: "
                                f"{error}"
                            )

                    consecutive_errors = 0
                    deadline_consecutive_errors = 0
                    retry_attempt = min(retry_attempt + 1, 3)
                    print(
                        "Timeout handled, continuing to listen for next user "
                        f"input on connection {connection_id}"
                    )
                    continue

                if receive_task in done:
                    try:
                        await receive_task
                        print(
                            "Response receiving completed normally for "
                            f"connection {connection_id}"
                        )
                        consecutive_errors = 0
                        deadline_consecutive_errors = 0
                        retry_attempt = 0
                        print(
                            "Turn completed successfully, continuing session "
                            f"for connection {connection_id}"
                        )
                        continue
                    except websockets.exceptions.ConnectionClosedOK:
                        print(
                            f"Connection {connection_id} closed normally, "
                            "stopping response handler"
                        )
                        break
                    except websockets.exceptions.ConnectionClosed as error:
                        print(f"Connection {connection_id} closed: {error}")
                        error_msg = str(error)
                        if (
                            "deadline expired before operation could complete"
                            in error_msg.lower()
                            or error.code == 1011
                        ):
                            deadline_consecutive_errors += 1
                            consecutive_errors += 1
                            print(
                                "Deadline error detected "
                                f"(deadline: {deadline_consecutive_errors}/"
                                f"{max_deadline_errors}, total: "
                                f"{consecutive_errors}/{max_consecutive_errors})"
                            )
                            api_usage_tracker.log_error(
                                str(connection_id),
                                "deadline_error",
                                error_msg,
                                is_deadline_error=True,
                            )
                            deadline_error = Exception(
                                f"Deadline expired error: {error_msg}"
                            )
                            should_retry, handler_msg = (
                                await api_error_handler.handle_api_error(
                                    deadline_error, connection_id, MODEL
                                )
                            )
                            if (
                                should_retry
                                and deadline_consecutive_errors < max_deadline_errors
                                and consecutive_errors < max_consecutive_errors
                            ):
                                print(f"API Error Handler: {handler_msg}")
                                if connection_monitor.is_websocket_open():
                                    await connection_monitor.safe_send(json.dumps({
                                        "text": (
                                            "Backend experiencing delays "
                                            f"(attempt {deadline_consecutive_errors}/"
                                            f"{max_deadline_errors}): {handler_msg}"
                                        ),
                                        "is_system_message": True,
                                    }))
                                retry_attempt += 1
                                continue

                            print(
                                "Too many consecutive deadline errors "
                                f"({deadline_consecutive_errors}) or handler "
                                f"recommends stopping: {handler_msg}"
                            )
                            if connection_monitor.is_websocket_open():
                                await connection_monitor.safe_send(json.dumps({
                                    "text": (
                                        f"Backend connection unstable: "
                                        f"{handler_msg}. Stopping attempts to "
                                        "prevent overload."
                                    ),
                                    "is_system_message": True,
                                    "is_error": True,
                                }))
                            break
                        break
                    except asyncio.CancelledError:
                        print(
                            "Response receiving task cancelled for connection "
                            f"{connection_id}"
                        )
                        break
                    except Exception as error:
                        consecutive_errors += 1
                        print(
                            "Error in response receiving task (consecutive: "
                            f"{consecutive_errors}/{max_consecutive_errors}): "
                            f"{error}"
                        )
                        api_usage_tracker.log_error(
                            str(connection_id),
                            "response_error",
                            str(error),
                            is_deadline_error=False,
                        )
                        should_retry, error_msg = (
                            await api_error_handler.handle_api_error(
                                error, connection_id, MODEL
                            )
                        )
                        if (
                            should_retry
                            and consecutive_errors < max_consecutive_errors
                        ):
                            print(f"API Error Handler: {error_msg}")
                            if connection_monitor.is_websocket_open():
                                await connection_monitor.safe_send(json.dumps({
                                    "text": (
                                        "Retrying after error (attempt "
                                        f"{consecutive_errors}/"
                                        f"{max_consecutive_errors}): {error_msg}"
                                    ),
                                    "is_system_message": True,
                                }))
                            retry_attempt += 1
                            continue

                        print(
                            f"Too many consecutive errors ({consecutive_errors}) "
                            "or handler recommends stopping: "
                            f"{error_msg}"
                        )
                        if connection_monitor.is_websocket_open():
                            await connection_monitor.safe_send(json.dumps({
                                "text": (
                                    "Connection error (stopping after "
                                    f"{consecutive_errors} attempts): {error_msg}"
                                ),
                                "is_system_message": True,
                                "is_error": True,
                            }))
                        break
            except Exception as error:
                consecutive_errors += 1
                print(
                    "Error in receive_from_gemini loop (consecutive: "
                    f"{consecutive_errors}/{max_consecutive_errors}): {error}"
                )
                api_usage_tracker.log_error(
                    str(connection_id),
                    "connection_error",
                    str(error),
                    is_deadline_error=False,
                )
                should_retry, error_msg = (
                    await api_error_handler.handle_api_error(
                        error, connection_id, MODEL
                    )
                )
                if should_retry and consecutive_errors < max_consecutive_errors:
                    print(f"API Error Handler: {error_msg}")
                    if connection_monitor.is_websocket_open():
                        await connection_monitor.safe_send(json.dumps({
                            "text": (
                                "Retrying connection (attempt "
                                f"{consecutive_errors}/"
                                f"{max_consecutive_errors}): {error_msg}"
                            ),
                            "is_system_message": True,
                        }))
                    retry_attempt += 1
                    continue

                print(
                    f"Stopping due to too many errors ({consecutive_errors}) "
                    f"or handler recommendation: {error_msg}"
                )
                if connection_monitor.is_websocket_open():
                    await connection_monitor.safe_send(json.dumps({
                        "text": (
                            "Connection failed after "
                            f"{consecutive_errors} attempts: {error_msg}"
                        ),
                        "is_system_message": True,
                        "is_error": True,
                    }))
                break
    except Exception as error:
        print(f"Critical error in receive_from_gemini: {error}")
        if connection_monitor.is_websocket_open():
            await connection_monitor.safe_send(json.dumps({
                "text": f"Critical connection error: {str(error)}",
                "is_system_message": True,
                "is_error": True,
            }))
    finally:
        response_handler.cancel_pending_tasks()
        stats = usage_monitor.get_stats()
        print(f"\nConnection {connection_id} usage statistics:")
        print(f"  Requests: {stats['requests']}")
        print(f"  Errors: {stats['errors']} (rate: {stats['error_rate']:.2%})")
        print(
            "  Deadline errors: "
            f"{stats['deadline_errors']} "
            f"(rate: {stats['deadline_error_rate']:.2%})"
        )

        if 'request_start_time' in locals():
            response_time = (
                asyncio.get_event_loop().time() - request_start_time
            )
            success = (
                consecutive_errors == 0 and deadline_consecutive_errors == 0
            )
            api_usage_tracker.log_request_completion(
                request_index, success, response_time
            )

        if receive_task and not receive_task.done():
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass
            except Exception as error:
                print(f"Error during final task cleanup: {error}")

        print(
            f"Persistent response handler for connection {connection_id} terminated"
        )
