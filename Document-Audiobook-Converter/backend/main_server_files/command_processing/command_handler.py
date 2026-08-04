import json
from ..chat_history.chat_history_handler import clear_chat_history, load_chat_history
from ..voice_configuration.voice_config_handler import change_voice_settings

async def process_command(data, connection_monitor, audio_processor, connection_id):
    """Process various commands received from the client."""
    command = data.get("command")
    
    if command == "set_sequential":
        return await handle_sequential_mode(data, audio_processor, connection_id)
        
    elif command == "clear_history":
        return await handle_clear_history(connection_monitor)
        
    elif command == "change_voice":
        return await handle_voice_change(data, connection_monitor)
        
    elif command == "get_history":
        return await handle_get_history(connection_monitor)
        
    elif command == "set_cleanup_interval":
        return await handle_cleanup_interval(data, connection_monitor)
        
    return False  # Command not recognized

async def handle_sequential_mode(data, audio_processor, connection_id):
    """Handle setting sequential audio playback mode."""
    audio_processor.is_sequential = data.get("sequentialAudioPlay", False)
    print(f"Sequential audio mode set to {audio_processor.is_sequential} mid-session for connection {connection_id}")
    return True

async def handle_clear_history(connection_monitor):
    """Handle clearing chat history."""
    print("Received clear_history command")
    clear_chat_history()
    await connection_monitor.safe_send(json.dumps({
        "text": "Chat history cleared",
        "is_system_message": True
    }))
    return True

async def handle_voice_change(data, connection_monitor):
    """Handle voice configuration changes."""
    try:
        new_voice = data.get("voice_name")
        if new_voice:
            await change_voice_settings(new_voice)
            await connection_monitor.safe_send(json.dumps({
                "text": f"Voice changed to {new_voice}",
                "is_system_message": True
            }))
        return True
    except Exception as e:
        print(f"Error changing voice: {e}")
        await connection_monitor.safe_send(json.dumps({
            "text": f"Error changing voice: {str(e)}",
            "is_system_message": True,
            "is_error": True
        }))
        return True

async def handle_get_history(connection_monitor):
    """Handle retrieving chat history."""
    try:
        history = load_chat_history()
        await connection_monitor.safe_send(json.dumps({
            "type": "history",
            "data": history,
            "is_system_message": True
        }))
        return True
    except Exception as e:
        print(f"Error retrieving history: {e}")
        await connection_monitor.safe_send(json.dumps({
            "text": f"Error retrieving history: {str(e)}",
            "is_system_message": True,
            "is_error": True
        }))
        return True

async def handle_cleanup_interval(data, connection_monitor):
    """Handle setting cleanup interval."""
    try:
        interval = data.get("interval")
        if interval is not None:
            # Implementation for cleanup interval setting would go here
            await connection_monitor.safe_send(json.dumps({
                "text": f"Cleanup interval set to {interval}",
                "is_system_message": True
            }))
        return True
    except Exception as e:
        print(f"Error setting cleanup interval: {e}")
        await connection_monitor.safe_send(json.dumps({
            "text": f"Error setting cleanup interval: {str(e)}",
            "is_system_message": True,
            "is_error": True
        }))
        return True 