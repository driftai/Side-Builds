"""
Re-exports the session initialization functionality from session_manager.
This file exists for backward compatibility.
"""

from .session_manager import create_gemini_session

# Re-export the create_gemini_session function
initialize_gemini_session = create_gemini_session