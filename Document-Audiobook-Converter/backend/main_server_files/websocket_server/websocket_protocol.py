"""Pure protocol helpers shared by the websocket session runtime.

The order in :func:`classify_client_message` is a compatibility contract. Older
clients often send payloads that match more than one shape, so classification
must continue to follow the original first-match routing order.
"""

import datetime


SETUP = "setup"
TYPED_PING = "typed_ping"
DISCONNECT = "disconnect"
TYPED_COMMAND = "typed_command"
STATUS = "status"
CONFIGURATION = "configuration"
TYPED_UNKNOWN = "typed_unknown"
REALTIME_INPUT = "realtime_input"
LEGACY_COMMAND = "legacy_command"
LEGACY_PING = "legacy_ping"
SILENT_TIME_UPDATE = "silent_time_update"
SILENT_UPDATE = "silent_update"
HISTORY = "history"
MEDIA = "media"
UNKNOWN = "unknown"

PING_TYPES = {"application_ping", "ping", "keepalive", "heartbeat"}
COMMAND_TYPES = {"command", "action", "request"}
STATUS_TYPES = {"status_update", "client_status", "connection_test"}
CONFIGURATION_TYPES = {"config", "settings", "preferences"}
LEGACY_COMMAND_KEYS = {
    "command", "clear_history", "voice_change", "get_history", "new_model", "action",
}
HISTORY_KEYS = {"history", "context", "conversation_history", "chat_context"}
MEDIA_KEYS = {"media", "audio", "video", "image", "file"}


def classify_client_message(data):
    """Return the original router's first matching message category."""
    if "setup" in data:
        return SETUP

    if "type" in data:
        message_type = data.get("type")
        if message_type in PING_TYPES:
            return TYPED_PING
        if message_type == "disconnect":
            return DISCONNECT
        if message_type in COMMAND_TYPES:
            return TYPED_COMMAND
        if message_type in STATUS_TYPES:
            return STATUS
        if message_type in CONFIGURATION_TYPES:
            return CONFIGURATION
        return TYPED_UNKNOWN

    if "realtime_input" in data:
        return REALTIME_INPUT
    if any(key in data for key in LEGACY_COMMAND_KEYS):
        return LEGACY_COMMAND
    # Deliberately use equality rather than identity: the legacy router also
    # accepted numeric ``1`` because ``1 == True`` in Python.
    if data.get("ping") == True or data.get("ping") == "ping":  # noqa: E712
        return LEGACY_PING
    if data.get("is_time_update") and data.get("is_silent_update"):
        return SILENT_TIME_UPDATE
    if data.get("is_silent_update") or data.get("silent"):
        return SILENT_UPDATE
    if any(key in data for key in HISTORY_KEYS):
        return HISTORY
    if any(key in data for key in MEDIA_KEYS):
        return MEDIA
    return UNKNOWN


def extract_setup_metadata(data):
    """Read the model and voice from the legacy nested setup payload."""
    setup_data = data.get("setup", {})
    if not setup_data:
        return setup_data, "gemini-2.0-flash-live-001", None

    model_name = setup_data.get("model", "gemini-2.0-flash-live-001")
    speech_config = setup_data.get("speechConfig", {})
    voice_config = speech_config.get("voiceConfig", {}) if speech_config else {}
    prebuilt_config = voice_config.get("prebuiltVoiceConfig", {}) if voice_config else {}
    voice_name = prebuilt_config.get("voiceName") if prebuilt_config else None
    return setup_data, model_name, voice_name


def format_history_message(message):
    """Build the client payload used when replaying one stored chat message."""
    timestamp = ""
    try:
        parsed = datetime.datetime.fromisoformat(message["timestamp"])
        timestamp = parsed.strftime("%m/%d/%Y %I:%M %p")
    except Exception as error:
        print(f"Error formatting timestamp: {error}")

    prefix = "YOU: " if message["role"] == "user" else "GEMINI: "
    return {
        "text": f"{prefix}{message['content']}",
        "timestamp": timestamp,
        "is_history": True,
    }


def build_history_context(chat_history, limit=10):
    """Translate stored chat messages into the Gemini context representation."""
    return [
        {
            "role": "user" if message["role"] == "user" else "model",
            "parts": [{"text": message["content"]}],
        }
        for message in chat_history[-limit:]
    ]
