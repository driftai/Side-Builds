"""
API initialization and status reporting functionality.
This module handles the initialization and status reporting of the Gemini API.
"""

import sys
import websockets
import google.generativeai as generative
from .gemini_config import MAIN_MODEL, TRANSCRIPTION_MODEL

def print_api_status():
    """Print API status information including versions and configuration."""
    print("\n====== STARTING SERVER ======")
    print(f"Python version: {sys.version}")
    print(f"Websockets version: {websockets.__version__}")
    print(f"Google Generative AI version: {generative.__version__}")
    
def print_api_initialization(api_key):
    """Print API initialization information."""
    print(f"\n====== INITIALIZATION ======")
    print(f"Starting server with API key: {api_key[:5]}...{api_key[-5:]} (length: {len(api_key)})")
    print(f"\nUsing models:")
    print(f"- Main model (multimodal): {MAIN_MODEL}")
    print(f"- Transcription model (text-only): {TRANSCRIPTION_MODEL}") 