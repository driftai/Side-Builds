"""Admission, compatibility commands, and configuration for a live session."""

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from main_server_files.api_configuration.gemini_config import create_gemini_config
from main_server_files.chat_history.chat_history_handler import (
    clear_chat_history,
    load_chat_history,
)
from main_server_files.session_management.session_manager import (
    MAIN_MODEL_SESSION_LIMIT,
    active_sessions,
    cleanup_resources,
    semaphore_acquired,
    session_semaphore,
)
from main_server_files.voice_configuration.voice_config_handler import (
    extract_voice_and_model_configuration,
)
from main_server_files.websocket_server.websocket_protocol import (
    build_history_context,
    format_history_message,
)


@dataclass(frozen=True)
class SlotAcquisition:
    """Whether admission acquired a slot and whether setup should continue."""

    acquired: bool
    proceed: bool


@dataclass(frozen=True)
class InitialConfiguration:
    """Result of consuming startup compatibility commands and the final config."""

    data: Any
    proceed: bool


@dataclass(frozen=True)
class PreparedConfiguration:
    """Validated values needed to open and run a Gemini session."""

    data: dict
    voice_name: str
    model_name: str
    instructions: str
    continuation_hint: str
    gemini_config: Any


async def acquire_connection_slot(connection_id, connection_monitor, error_handler):
    """Preserve the handler's original semaphore admission sequence."""
    if not session_semaphore.locked() and session_semaphore._value <= 0:
        await error_handler.handle_session_slot_error(
            "max_reached", MAIN_MODEL_SESSION_LIMIT,
        )
        return SlotAcquisition(False, False)

    acquire_timeout = 30
    acquired = False
    try:
        if connection_monitor.is_websocket_open():
            await connection_monitor.safe_send(json.dumps({
                "text": (
                    "Waiting for an available session slot "
                    f"(timeout: {acquire_timeout}s)..."
                ),
                "is_system_message": True,
            }))
        else:
            await error_handler.handle_session_slot_error("closed_before_acquire")
            return SlotAcquisition(False, False)

        try:
            acquire_success = await asyncio.wait_for(
                session_semaphore.acquire(), timeout=acquire_timeout,
            )
            if acquire_success:
                semaphore_acquired.add(connection_id)
                acquired = True
        except asyncio.TimeoutError:
            acquire_success = False

        if not acquire_success:
            await error_handler.handle_session_slot_error("timeout")
            return SlotAcquisition(acquired, False)

        print(f"Acquired session slot for connection {connection_id}")
        if connection_monitor.is_websocket_open():
            await connection_monitor.safe_send(json.dumps({
                "text": "Session slot acquired. Proceeding with connection...",
                "is_system_message": True,
            }))
        else:
            print(f"Connection {connection_id} closed after acquiring semaphore")
            await cleanup_resources(connection_id)
            return SlotAcquisition(acquired, False)
    except Exception:
        await error_handler.handle_session_slot_error("acquire_error")
        return SlotAcquisition(acquired, False)

    return SlotAcquisition(acquired, True)


async def _receive_json(websocket, timeout):
    message = await asyncio.wait_for(websocket.recv(), timeout=timeout)
    return json.loads(message)


async def _replay_history(connection_monitor):
    chat_history = load_chat_history()
    if chat_history:
        await connection_monitor.safe_send(json.dumps({
            "text": "Restoring chat history...",
            "is_system_message": True,
        }))
        for message in chat_history:
            await connection_monitor.safe_send(json.dumps(
                format_history_message(message),
            ))
            await asyncio.sleep(0.1)
        return

    await connection_monitor.safe_send(json.dumps({
        "text": "No chat history found",
        "is_system_message": True,
    }))


async def receive_initial_configuration(
    websocket,
    connection_monitor,
    connection_id,
    error_handler,
):
    """Consume startup commands in their established compatibility order."""
    config_data = await _receive_json(websocket, 30)
    print(f"Configuration received for connection: {connection_id}")

    if config_data.get("command") == "clear_history":
        print("Received clear_history command at session start")
        clear_chat_history()
        await connection_monitor.safe_send(json.dumps({
            "text": "Chat history cleared",
            "is_system_message": True,
        }))
        config_data = await _receive_json(websocket, 30)
        print("Configuration received after history clear")

    if config_data.get("command") == "get_history":
        print("Received get_history command at session start")
        await _replay_history(connection_monitor)
        config_data = await _receive_json(websocket, 30)
        print("Configuration received after history request")

    if config_data.get("command") == "close_session":
        print("Received close session command - waiting for new voice config")
        try:
            config_data = await _receive_json(websocket, 10)
            print("New voice configuration received")
            await connection_monitor.safe_send(json.dumps({
                "text": (
                    "Voice change request received, applying new voice "
                    "configuration..."
                ),
                "is_system_message": True,
            }))

            if (
                connection_id in active_sessions
                and active_sessions[connection_id].get("session")
            ):
                try:
                    print(
                        f"Closing existing session for connection {connection_id} "
                        "to change voice"
                    )
                except Exception as error:
                    await error_handler.handle_session_close_error(error)

            if connection_id in active_sessions:
                del active_sessions[connection_id]
                print(
                    f"Removed connection {connection_id} from active sessions "
                    "for voice change"
                )
        except asyncio.TimeoutError:
            await error_handler.handle_voice_config_timeout()
            return InitialConfiguration(config_data, False)
        except Exception as error:
            await error_handler.handle_voice_change_error(error)
            return InitialConfiguration(config_data, False)

    return InitialConfiguration(config_data, True)


async def prepare_configuration(config_data, error_handler):
    """Validate client choices and build the Gemini connection config."""
    client_config = extract_voice_and_model_configuration(config_data)
    voice_name = client_config["voice_name"]
    model_name = client_config["model_name"]
    allow_model_override = client_config["allow_override"]
    instructions = config_data.get("instructions", "")
    continuation_hint = config_data.get("continuationHint", "")

    from main_server_files.api_configuration.gemini_config import (
        ALLOW_CLIENT_MODEL_OVERRIDE,
        MODEL_VALIDATION_ENABLED,
        get_allowed_models_list,
        validate_model,
    )

    if MODEL_VALIDATION_ENABLED:
        if allow_model_override and not ALLOW_CLIENT_MODEL_OVERRIDE:
            await error_handler.handle_model_validation_error(
                "Client requested model override but server has disabled "
                "model override functionality"
            )
            return None
        if allow_model_override and not validate_model(
            model_name, allow_override=True,
        ):
            await error_handler.handle_model_validation_error(
                f"Client requested invalid model '{model_name}'. Allowed models: "
                f"{get_allowed_models_list()}"
            )
            return None

    # This context was built by the original handler even though the current
    # Live config only consumes instructions and continuity. Retain the read and
    # transformation so startup side effects and compatibility stay unchanged.
    build_history_context(load_chat_history())

    gemini_config = create_gemini_config(
        voice_name=voice_name,
        instructions=instructions,
        continuation_hint=continuation_hint,
    )
    print(
        f"Created configuration with voice: {voice_name} and instructions: "
        f"{bool(instructions)}"
        + (
            f", continuing from {len(continuation_hint)} chars of previous passage"
            if continuation_hint else ""
        )
    )
    return PreparedConfiguration(
        data=config_data,
        voice_name=voice_name,
        model_name=model_name,
        instructions=instructions,
        continuation_hint=continuation_hint,
        gemini_config=gemini_config,
    )


def initialize_session_client(prepared):
    """Create the API client after the client has been told we are connecting."""
    from main_server_files.api_configuration.api_client_manager import (
        initialize_api_client,
    )

    return initialize_api_client(
        prepared.model_name,
        client_key=prepared.data.get("apiKey"),
    )
