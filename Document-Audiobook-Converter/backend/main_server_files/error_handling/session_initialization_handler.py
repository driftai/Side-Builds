"""
Handles errors that occur during Gemini session initialization.
This module provides specialized error handling for the session initialization process,
working in conjunction with the APIErrorHandler for API-specific errors.
"""

import json
import asyncio
from typing import Optional, Any, Callable, Awaitable
from .api_error_handler import APIErrorHandler

async def handle_session_initialization_error(
    e: Exception,
    connection_id: str,
    safe_send: Callable[[str], Awaitable[None]],
    api_error_handler: APIErrorHandler,
    model_name: str = ""
) -> Optional[Any]:
    """
    Handle errors that occur during Gemini session initialization.
    
    This function handles both API-specific errors and general initialization errors,
    providing appropriate error messages and retry information to the client.
    
    Args:
        e: The exception that occurred during initialization
        connection_id: Unique identifier for the connection
        safe_send: Async function to safely send messages to the client
        api_error_handler: The APIErrorHandler instance
        model_name: Name of the model being used for better error handling
        
    Returns:
        Optional[Any]: None to indicate initialization failure
    """
    try:
        # Use the instance passed as a parameter with model name for better error classification
        should_retry, error_msg = await api_error_handler.handle_api_error(e, connection_id, model_name)
        print(f"Error connecting to Gemini API ({model_name}): {error_msg}")
        
        # Enhanced error message for preview models
        if "preview" in model_name.lower() or "experimental" in model_name.lower():
            enhanced_msg = f"Error connecting to {model_name}: {error_msg}. Note: Preview models can be unstable and may require multiple connection attempts."
        else:
            enhanced_msg = f"Error connecting to Gemini API: {error_msg}"
            
        await safe_send(json.dumps({
            "text": enhanced_msg,
            "is_system_message": True,
            "is_error": True,
            "should_retry": should_retry,
            "model_name": model_name
        }))
        return None
    except Exception as e: # Catch potential errors during error handling itself
        print(f"Error during session initialization error handling: {e}")
        await safe_send(json.dumps({
            "text": f"An unexpected error occurred during session setup: {str(e)}",
            "is_system_message": True,
            "is_error": True
        }))
        return None 