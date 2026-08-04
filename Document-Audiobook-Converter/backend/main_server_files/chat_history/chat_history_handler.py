import json
import os
import datetime
from ..server_initialization.server_config import CHAT_HISTORY_FILE

def save_chat_history(message, is_user=False):
    """Save a message to chat history"""
    try:
        history = []
        if os.path.exists(CHAT_HISTORY_FILE):
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        
        history.append({
            'timestamp': datetime.datetime.now().isoformat(),
            'role': 'user' if is_user else 'gemini',
            'content': message
        })
        
        with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        print(f"Error saving chat history: {e}")

def load_chat_history():
    """Load chat history from file"""
    try:
        if os.path.exists(CHAT_HISTORY_FILE):
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Error loading chat history: {e}")
        return []

def clear_chat_history():
    """Clear the chat history file"""
    try:
        if os.path.exists(CHAT_HISTORY_FILE):
            with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump([], f)
            print("Chat history cleared successfully")
    except Exception as e:
        print(f"Error clearing chat history: {e}") 