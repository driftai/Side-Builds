import json
import asyncio
from ..error_handling.api_error_handler import api_error_handler
from ..api_configuration.gemini_config import create_gemini_config, MAIN_MODEL as MODEL
from ..chat_history.chat_history_handler import load_chat_history

async def reconnect_to_gemini(client, voice_name, websocket, safe_send, connection_id, initialize_gemini_session=None):
    """Attempt to reconnect to Gemini API with enhanced error handling and exponential backoff."""
    # Build context from chat history
    chat_history = load_chat_history()
    context = []
    for msg in chat_history[-10:]:  # Use last 10 messages for context
        context.append({
            "role": "user" if msg['role'] == 'user' else "model",
            "parts": [{"text": msg['content']}]
        })
    
    try:
        # Try to connect to Gemini API with config
        if initialize_gemini_session:
            # Use provided initialization function
            session = await initialize_gemini_session(
                client=client,
                voice_name=voice_name,
                context=context,
                websocket=websocket,
                safe_send=safe_send,
                model=MODEL,
                connection_id=connection_id
            )
        else:
            # Use default initialization
            config = create_gemini_config(voice_name=voice_name)
            session = await client.aio.live.connect(model=MODEL, config=config)
        
        if session:
            print(f"Reconnected to Gemini API for connection: {connection_id}")
            api_error_handler.reset_error_count(connection_id)
            await safe_send(json.dumps({
                "text": "Reconnected to Gemini API successfully",
                "is_system_message": True
            }))
            return session
            
        # If we get here and don't have a session, use enhanced error handler
        should_retry, error_msg = await api_error_handler.handle_api_error(
            Exception("Session initialization failed"), connection_id, MODEL
        )
        if not should_retry:
            await safe_send(json.dumps({
                "text": "Failed to reconnect: " + error_msg,
                "is_system_message": True,
                "is_error": True
            }))
            return None
            
        await safe_send(json.dumps({
            "text": f"Retrying connection: {error_msg}",
            "is_system_message": True
        }))
        
    except Exception as e:
        # Use enhanced error handler to determine retry strategy
        should_retry, error_msg = await api_error_handler.handle_api_error(e, connection_id, MODEL)
        
        if not should_retry:
            await safe_send(json.dumps({
                "text": "Failed to reconnect: " + error_msg,
                "is_system_message": True,
                "is_error": True
            }))
            return None
        
        print(f"Error during reconnection (will retry): {error_msg}")
        await safe_send(json.dumps({
            "text": f"Retrying connection: {error_msg}",
            "is_system_message": True
        }))
        
        # The error handler already applied appropriate delays, so we can continue
    
    return None 