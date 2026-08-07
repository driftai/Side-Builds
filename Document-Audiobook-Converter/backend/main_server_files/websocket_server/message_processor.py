"""Compatibility facade for client-to-Gemini websocket messages."""

from main_server_files.websocket_server.message_runtime import run_send_to_gemini


async def send_to_gemini(
    session,
    websocket,
    connection_monitor,
    connection_id,
    audio_processor,
    client=None,
):
    """Send client websocket messages to Gemini.

    This public async entrypoint retains its established name, positional
    arguments, and optional client argument. Routing and retry ownership live in
    focused modules so callers do not need to change.
    """
    return await run_send_to_gemini(
        session,
        websocket,
        connection_monitor,
        connection_id,
        audio_processor,
        client,
    )
