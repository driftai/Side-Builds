"""
Error handling package for the Gemini Chat Interface
"""

from .api_error_handler import APIErrorHandler # For creating the instance

# Create a singleton instance FIRST
api_error_handler = APIErrorHandler()

# THEN import other modules from this package that might use the instance
from .session_initialization_handler import handle_session_initialization_error

__all__ = [
    'APIErrorHandler',
    'api_error_handler', # The instance
    'handle_session_initialization_error'
] 