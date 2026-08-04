"""
Manages Gemini session initialization and configuration.
This module handles the core logic for creating and configuring new Gemini sessions.
"""

import asyncio
import datetime
import time
import websockets
import json
import traceback
from ..error_handling.api_error_handler import api_error_handler
# Removed circular import - will import locally where needed
from ..api_configuration.gemini_config import (
    MAIN_MODEL as MODEL,
    TRANSCRIPTION_MODEL,
    create_gemini_config
)
from ..error_handling.session_initialization_handler import handle_session_initialization_error

# Track active sessions to help with cleanup
active_sessions = {}

# Track which connections have acquired a semaphore
semaphore_acquired = set()

# Model-specific concurrent session limits.
# Reference: https://ai.google.dev/gemini-api/docs/rate-limits
#
# These were all set to 1, which is stricter than Google actually enforces and
# caused real starvation: a single long-lived session (the config panel's test
# connection, or another app pointed at this same server) held the only slot,
# and every other connection sat in the 30s acquire queue and timed out with
# "Timeout waiting for an available session".
#
# Measured 2026-08-03 by opening concurrent live sessions directly against
# Google: 4 simultaneous sessions all connected, while a separate app already
# held one. Limit set to 3 - enough for a playback socket, the config panel's
# test connection, and a second client, with headroom under the observed ceiling.
MODEL_SESSION_LIMITS = {
    "gemini-2.5-flash-native-audio-latest": 3,
    "gemini-2.5-flash-native-audio-preview-09-2025": 3,
    "gemini-2.5-flash-native-audio-preview-12-2025": 3,
    "gemini-3.1-flash-live-preview": 3,
    "default": 3
}

# Get the appropriate session limit for the current model
def get_session_limit_for_model(model_name):
    """Get the concurrent session limit for a specific model."""
    model_lower = model_name.lower()
    for model_pattern, limit in MODEL_SESSION_LIMITS.items():
        if model_pattern in model_lower:
            return limit
    return MODEL_SESSION_LIMITS["default"]

# Set up model-specific semaphore based on the main model
MAIN_MODEL_SESSION_LIMIT = get_session_limit_for_model(MODEL)
session_semaphore = asyncio.Semaphore(MAIN_MODEL_SESSION_LIMIT)

print(f"Session limit for {MODEL}: {MAIN_MODEL_SESSION_LIMIT} concurrent session(s)")

async def safe_send(websocket, message, connection_id):
    """Helper function to safely send a message to the websocket."""
    try:
        if websocket.state in (websockets.protocol.State.CLOSED, websockets.protocol.State.CLOSING):
            print(f"WebSocket is closed (state: {websocket.state}) for connection {connection_id}")
            return False
            
        await websocket.send(message)
        return True
    except Exception as e:
        print(f"Error sending message to connection {connection_id}: {e}")
        return False

async def cleanup_resources(connection_id: str):
    """Clean up resources for a connection"""
    try:
        # Clean up error tracking
        api_error_handler.cleanup_connection(connection_id)

        # Clean up session data
        if connection_id in active_sessions:
            print(f"Cleaning up resources for connection: {connection_id}")
            del active_sessions[connection_id]

        # Handle semaphore release
        if connection_id in semaphore_acquired:
            print(f"Releasing semaphore for connection: {connection_id}")
            semaphore_acquired.remove(connection_id)
            session_semaphore.release()
            print(f"Released session semaphore, available slots: {session_semaphore._value}")

        # Clear chat history after each connection to prevent buildup
        print(f"Clearing chat history after connection {connection_id}")
        try:
            from ..chat_history.chat_history_handler import clear_chat_history
            clear_chat_history()
        except ImportError as e:
            print(f"Warning: Could not clear chat history due to import error: {e}")

        print(f"Active sessions after cleanup: {len(active_sessions)}")
        print(f"Connections with semaphores: {len(semaphore_acquired)}")
    except Exception as e:
        print(f"Error during cleanup for connection {connection_id}: {e}")
        traceback.print_exc()

async def acquire_session_slot(websocket, connection_id, timeout=30):
    """Attempt to acquire a session slot with timeout."""
    try:
        if not session_semaphore.locked() and session_semaphore._value <= 0:
            print(f"Maximum concurrent sessions reached ({MAIN_MODEL_SESSION_LIMIT}). Connection {connection_id} will wait.")
            await safe_send(websocket, json.dumps({
                "text": f"Server is at maximum capacity ({MAIN_MODEL_SESSION_LIMIT} concurrent sessions). Please wait or try again later.",
                "is_system_message": True,
                "is_error": True
            }), connection_id)
        
        # Send a message to the client that they're in queue
        if websocket.state not in (websockets.protocol.State.CLOSED, websockets.protocol.State.CLOSING):
            await safe_send(websocket, json.dumps({
                "text": f"Waiting for an available session slot (timeout: {timeout}s)...",
                "is_system_message": True
            }), connection_id)
        else:
            print(f"Connection {connection_id} closed before acquiring semaphore")
            return False
        
        # Try to acquire the semaphore with a timeout
        try:
            acquire_success = await asyncio.wait_for(session_semaphore.acquire(), timeout=timeout)
            if acquire_success:
                semaphore_acquired.add(connection_id)
                print(f"Acquired session slot for connection {connection_id}")
                if websocket.state not in (websockets.protocol.State.CLOSED, websockets.protocol.State.CLOSING):
                    await safe_send(websocket, json.dumps({
                        "text": "Session slot acquired. Proceeding with connection...",
                        "is_system_message": True
                    }), connection_id)
                return True
        except asyncio.TimeoutError:
            acquire_success = False
        
        if not acquire_success:
            print(f"Timeout waiting for session slot for connection {connection_id}")
            if websocket.state not in (websockets.protocol.State.CLOSED, websockets.protocol.State.CLOSING):
                await safe_send(websocket, json.dumps({
                    "text": "Timeout waiting for an available session. Please try again later.",
                    "is_system_message": True,
                    "is_error": True
                }), connection_id)
            return False
            
    except Exception as e:
        print(f"Error acquiring session semaphore: {e}")
        await safe_send(websocket, json.dumps({
            "text": "Error acquiring session slot. Please try again.",
            "is_system_message": True,
            "is_error": True
        }), connection_id)
        return False

async def periodic_cleanup(cleanup_interval_sec):
    """Perform periodic cleanup of inactive sessions."""
    while True:
        try:
            await asyncio.sleep(cleanup_interval_sec)
            print("\n=== Periodic Session Cleanup ===")
            print(f"Active sessions before cleanup: {len(active_sessions)}")
            print(f"Connections with semaphores: {len(semaphore_acquired)}")
            
            # Check for orphaned semaphores
            for conn_id in list(semaphore_acquired):
                if conn_id not in active_sessions:
                    print(f"Found orphaned semaphore for connection {conn_id}, releasing")
                    semaphore_acquired.remove(conn_id)
                    session_semaphore.release()
            
            # Check for dead connections
            for conn_id in list(active_sessions.keys()):
                session_info = active_sessions[conn_id]
                connected_at = session_info.get("connected_at", "unknown")
                last_active = session_info.get("last_active", 0)
                
                # If a connection hasn't been active for 5 minutes, consider it dead
                if time.time() - last_active > 300:
                    print(f"Connection {conn_id} inactive for >5 minutes, removing from active sessions")
                    if conn_id in active_sessions:
                        del active_sessions[conn_id]
                    
                    if conn_id in semaphore_acquired:
                        print(f"Releasing semaphore for inactive connection: {conn_id}")
                        semaphore_acquired.remove(conn_id)
                        session_semaphore.release()
                        print(f"Released session semaphore, available slots: {session_semaphore._value}")
            
            # Log active sessions
            for conn_id, session_info in list(active_sessions.items()):
                connected_at = session_info.get("connected_at", "unknown")
                print(f"Session {conn_id} connected at {connected_at}")
            print("=== Cleanup Complete ===\n")
        except Exception as e:
            print(f"Error in periodic cleanup: {e}")

def register_active_session(connection_id, websocket):
    """Register a new active session."""
    active_sessions[connection_id] = {
        "connected_at": datetime.datetime.now().isoformat(),
        "last_active": time.time(),
        "remote": str(websocket.remote_address) if hasattr(websocket, 'remote_address') else "unknown"
    }

def update_session_activity(connection_id):
    """Update the last activity timestamp for a session."""
    if connection_id in active_sessions:
        active_sessions[connection_id]["last_active"] = time.time()

def get_active_sessions():
    """Get the current active sessions."""
    return active_sessions

def get_session_info(connection_id):
    """Get information about a specific session."""
    return active_sessions.get(connection_id)

async def create_gemini_session(client, voice_name, context, websocket, safe_send, model, connection_id):
    """
    Create and initialize a new Gemini session with the given configuration.
    Enhanced with retry logic for experimental models.

    Args:
        client: The Gemini API client instance
        voice_name: Name of the voice to use for responses
        context: Optional context for the session
        websocket: WebSocket connection instance
        safe_send: Function to safely send messages to the client
        model: The Gemini model to use
        connection_id: Unique identifier for the connection

    Returns:
        The initialized Gemini session or None if initialization fails
    """
    try:
        # Create configuration using the centralized config creator
        config = create_gemini_config(voice_name=voice_name)
        print(f"Initializing Gemini session with voice: {voice_name}, model: {model}")
        
        # Enhanced retry logic for preview models
        is_preview_model = any(keyword in model.lower() for keyword in ["preview", "experimental", "beta", "alpha"])
        is_native_audio_dialog = "native-audio-dialog" in model.lower()
        
        # Set retry parameters based on model type
        if is_native_audio_dialog:
            max_retries = 5  # More retries for the problematic native-audio-dialog model
            retry_delays = [2, 5, 10, 15, 20]  # Progressive backoff
        elif is_preview_model:
            max_retries = 4
            retry_delays = [1, 3, 7, 12]
        else:
            max_retries = 2
            retry_delays = [1, 3]
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    delay = retry_delays[min(attempt-1, len(retry_delays)-1)]
                    print(f"Retrying connection attempt {attempt+1}/{max_retries} for {model} after {delay}s delay...")
                    
                    # Send specific retry message for native-audio-dialog
                    if is_native_audio_dialog:
                        await safe_send(json.dumps({
                            "text": f"Retrying connection to {model} (attempt {attempt+1}/{max_retries}). This model is highly experimental and often requires multiple attempts...",
                            "is_system_message": True
                        }))
                    else:
                        await safe_send(json.dumps({
                            "text": f"Retrying connection to {model} (attempt {attempt+1}/{max_retries})...",
                            "is_system_message": True
                        }))
                    
                    await asyncio.sleep(delay)
                
                print(f"Connecting to Gemini API for connection: {connection_id} using model: {model}")
                session = await client.aio.live.connect(model=model, config=config)
                print(f"Connected to Gemini API with voice: {voice_name}, model: {model}")

                # Reset error count on successful connection using the singleton instance
                api_error_handler.reset_error_count(connection_id)

                # Send success message to client
                success_msg = f"Successfully connected to {model}"
                if is_native_audio_dialog:
                    success_msg += " (experimental native audio dialog model)"

                await safe_send(json.dumps({
                    "text": success_msg,
                    "is_system_message": True
                }))

                return session
                
            except Exception as e:
                error_msg = str(e).lower()
                print(f"Connection attempt {attempt+1} failed for {model}: {e}")
                
                # Check for specific errors and provide helpful messages
                if is_native_audio_dialog:
                    if "session creation failed" in error_msg or "connection" in error_msg:
                        print(f"Native audio dialog model connection issue (attempt {attempt+1}): {e}")
                        await safe_send(json.dumps({
                            "text": f"Connection issue with {model} (attempt {attempt+1}). This highly experimental model has known stability issues...",
                            "is_system_message": True
                        }))
                    elif "quota" in error_msg or "rate" in error_msg:
                        print(f"Quota/rate limit issue with {model}: {e}")
                        await safe_send(json.dumps({
                            "text": f"Rate limit reached for {model}. This model has stricter limits due to its experimental nature...",
                            "is_system_message": True
                        }))
                elif is_preview_model:
                    if "quota" in error_msg:
                        print(f"API quota exceeded for {model}, waiting before retry...")
                        await safe_send(json.dumps({
                            "text": f"API quota exceeded for {model}. Retrying in a moment...",
                            "is_system_message": True
                        }))
                    elif "connection" in error_msg or "timeout" in error_msg:
                        print(f"Connection issue with preview model {model}, retrying...")
                        await safe_send(json.dumps({
                            "text": f"Connection issue with {model}. Preview models can be unstable. Retrying...",
                            "is_system_message": True
                        }))
                    elif "session" in error_msg or "unavailable" in error_msg:
                        print(f"Session creation failed for preview model {model}, retrying...")
                        await safe_send(json.dumps({
                            "text": f"Session creation failed for {model}. Preview models may have intermittent issues. Retrying...",
                            "is_system_message": True
                        }))
                
                # If this is the last attempt, handle the error normally
                if attempt == max_retries - 1:
                    # Send model-specific guidance
                    if is_native_audio_dialog:
                        await safe_send(json.dumps({
                            "text": f"Failed to connect to {model} after {max_retries} attempts. This experimental native audio model is known to be highly unstable. Please try again in a few moments or consider using a more stable model.",
                            "is_system_message": True,
                            "is_error": True
                        }))
                    elif is_preview_model:
                        await safe_send(json.dumps({
                            "text": f"Failed to connect to {model} after {max_retries} attempts. This preview model may be experiencing issues. You can try again in a few moments.",
                            "is_system_message": True,
                            "is_error": True
                        }))
                    
                    # Pass model name to error handler
                    return await handle_session_initialization_error(e, connection_id, safe_send, api_error_handler, model)
        
        # If we get here, all retries failed
        return None
            
    except Exception as e:
        # Pass the api_error_handler instance and model name
        return await handle_session_initialization_error(e, connection_id, safe_send, api_error_handler, model) 