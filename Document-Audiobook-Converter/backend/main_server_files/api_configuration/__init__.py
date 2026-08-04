"""
API configuration package.
Provides functionality for managing Gemini API configuration and initialization.
"""

from .api_initialization import print_api_status, print_api_initialization
from .gemini_config import configure_gemini_api, create_gemini_client, create_gemini_config, MAIN_MODEL, TRANSCRIPTION_MODEL
from .api_key_manager import get_api_key, validate_api_key
from .api_client_manager import initialize_api_client, setup_api_environment

__all__ = [
    'print_api_status',
    'print_api_initialization',
    'configure_gemini_api',
    'create_gemini_client',
    'create_gemini_config',
    'MAIN_MODEL',
    'TRANSCRIPTION_MODEL',
    'get_api_key',
    'validate_api_key',
    'initialize_api_client',
    'setup_api_environment'
] 