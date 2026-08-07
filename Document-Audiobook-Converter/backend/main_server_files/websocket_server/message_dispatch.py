"""Classification-aware dispatch for one decoded client websocket message."""

import json
import time

from main_server_files.command_processing import process_command
from main_server_files.media_processing.realtime_input_processor import (
    process_realtime_input,
)
from main_server_files.session_management.session_manager import active_sessions
from main_server_files.websocket_server.websocket_protocol import (
    CONFIGURATION,
    DISCONNECT,
    HISTORY,
    LEGACY_COMMAND,
    LEGACY_PING,
    MEDIA,
    REALTIME_INPUT,
    SETUP,
    SILENT_TIME_UPDATE,
    SILENT_UPDATE,
    STATUS,
    TYPED_COMMAND,
    TYPED_PING,
    TYPED_UNKNOWN,
    classify_client_message,
    extract_setup_metadata,
)


async def _dispatch_setup(data, connection_monitor, connection_id, registry):
    print("Received client setup configuration message")
    setup_data, model_name, voice_name = extract_setup_metadata(data)
    if setup_data:
        print(f"Extracted from setup - Model: {model_name}, Voice: {voice_name}")
        if connection_id in registry:
            registry[connection_id]["model"] = model_name
            if voice_name:
                registry[connection_id]["voice_name"] = voice_name

    try:
        await connection_monitor.safe_send(json.dumps({
            "type": "setup_acknowledgment",
            "message": "Setup configuration received",
            "timestamp": time.time(),
        }))
    except Exception as error:
        print(f"Warning: Could not send setup acknowledgment: {error}")


async def _dispatch_typed(
    kind,
    data,
    session,
    connection_monitor,
    connection_id,
    audio_processor,
    command_handler,
):
    message_type = data.get("type")
    if kind == TYPED_PING:
        print(f"Received {message_type} from client, sending pong response")
        await connection_monitor.safe_send(json.dumps({
            "type": "application_pong",
            "message": "pong",
            "timestamp": data.get("timestamp"),
            "server_timestamp": time.time(),
            "client_id": connection_id,
        }))
        return True

    if kind == DISCONNECT:
        print(
            f"Client {connection_id} asked to disconnect; closing Gemini session"
        )
        try:
            if session is not None and hasattr(session, "close"):
                await session.close()
                print(f"Gemini session closed cleanly for {connection_id}")
        except Exception as error:
            print(f"Could not close Gemini session cleanly: {error}")
        return False

    if kind == TYPED_COMMAND:
        print(
            "Processing typed command: "
            f"{data.get('command', data.get('action', 'unknown'))}"
        )
        await command_handler(
            data, connection_monitor, audio_processor, connection_id,
        )
        return True

    if kind == STATUS:
        print(f"Received client status message: {message_type}")
        await connection_monitor.safe_send(json.dumps({
            "type": "status_acknowledgment",
            "received_type": message_type,
            "server_status": "active",
            "timestamp": time.time(),
        }))
        return True

    if kind == CONFIGURATION:
        print(f"Received configuration message: {message_type}")
        await command_handler(
            data, connection_monitor, audio_processor, connection_id,
        )
        return True

    if kind == TYPED_UNKNOWN:
        print(f"Received typed message with unrecognized type: {message_type}")
        try:
            await command_handler(
                data, connection_monitor, audio_processor, connection_id,
            )
        except Exception as error:
            print(f"Fallback processing failed for typed message: {error}")
        return True

    raise ValueError(f"Unsupported typed message category: {kind}")


async def _dispatch_unknown(
    data,
    connection_monitor,
    connection_id,
    audio_processor,
    command_handler,
):
    message_keys = sorted(data.keys())
    message_size = len(str(data))
    if not message_keys or message_size <= 10:
        print(f"WARNING: Received malformed or empty message: {data}")
        return

    print(
        "INFO: Processing unrecognized message structure with keys: "
        f"{message_keys}"
    )
    rendered = str(data)
    preview = rendered[:100] + ("..." if len(rendered) > 100 else "")
    print(f"Message preview: {preview}")
    try:
        await command_handler(
            data, connection_monitor, audio_processor, connection_id,
        )
        print("Successfully processed unrecognized message as command")
    except Exception as error:
        print(f"Could not process unrecognized message: {error}")
        await connection_monitor.safe_send(json.dumps({
            "type": "processing_error",
            "message": "Message format not recognized",
            "received_keys": message_keys,
            "timestamp": time.time(),
        }))


async def dispatch_client_message(
    data,
    session,
    connection_monitor,
    connection_id,
    audio_processor,
    *,
    command_handler=process_command,
    realtime_handler=process_realtime_input,
    session_registry=active_sessions,
):
    """Dispatch one decoded message; return False only for explicit disconnect."""
    kind = classify_client_message(data)

    if kind == SETUP:
        await _dispatch_setup(
            data, connection_monitor, connection_id, session_registry,
        )
        return True

    if kind in {
        TYPED_PING,
        DISCONNECT,
        TYPED_COMMAND,
        STATUS,
        CONFIGURATION,
        TYPED_UNKNOWN,
    }:
        return await _dispatch_typed(
            kind,
            data,
            session,
            connection_monitor,
            connection_id,
            audio_processor,
            command_handler,
        )

    if kind == REALTIME_INPUT:
        await realtime_handler(
            data, session, connection_monitor, audio_processor,
        )
        return True

    if kind == LEGACY_COMMAND:
        print(
            "Processing legacy command: "
            f"{data.get('command', data.get('action', 'legacy_command'))}"
        )
        await command_handler(
            data, connection_monitor, audio_processor, connection_id,
        )
        return True

    if kind == LEGACY_PING:
        print("Received legacy ping format from client, sending pong")
        await connection_monitor.safe_send(json.dumps({
            "pong": True,
            "timestamp": time.time(),
            "server_time": time.time(),
        }))
        return True

    if kind in {SILENT_TIME_UPDATE, SILENT_UPDATE}:
        return True

    if kind == HISTORY:
        print("Received chat history/context message")
        await command_handler(
            data, connection_monitor, audio_processor, connection_id,
        )
        return True

    if kind == MEDIA:
        print("Received media/multimodal message")
        try:
            await realtime_handler(
                data, session, connection_monitor, audio_processor,
            )
        except Exception as error:
            print(
                "Media processing failed, trying command processing: "
                f"{error}"
            )
            await command_handler(
                data, connection_monitor, audio_processor, connection_id,
            )
        return True

    await _dispatch_unknown(
        data,
        connection_monitor,
        connection_id,
        audio_processor,
        command_handler,
    )
    return True
