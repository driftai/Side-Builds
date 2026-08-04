"""
API client manager module.
Handles the initialization and setup of the Gemini API client.
"""

import sys
from .api_key_manager import get_api_key, validate_api_key, describe_key_source
from .api_initialization import print_api_initialization, print_api_status
from .gemini_config import configure_gemini_api, create_gemini_client

def initialize_api_client(model_name=None, client_key=None):
    """
    Initialize and configure the Gemini API client.
    Args:
        model_name: The model name to determine API version (optional)
        client_key: API key supplied by the connecting client (optional).
            Takes priority over the environment/.env.local/fallback key.
    Returns:
        The configured Gemini client instance
    """
    try:
        # Get API key from the api_key_manager (client key wins if valid)
        api_key = get_api_key(client_key)
        print(f"Using API key from: {describe_key_source(client_key)}")

        # Validate API key
        if not validate_api_key(api_key):
            print("\n====== ERROR: NO USABLE GEMINI API KEY ======")
            print("This project ships without a key on purpose.")
            print("\nGet one at https://aistudio.google.com/apikey, then either:")
            print("  - set the GEMINI_API_KEY environment variable, or")
            print("  - put GEMINI_API_KEY=... in .env.local at the project root, or")
            print("  - paste it into the app's Gemini settings panel")
            print("\nThe server will now exit.")
            sys.exit(1)

        # Print API initialization information and configure API
        print_api_initialization(api_key)
        configure_gemini_api(api_key)

        # Create and return the client with model-specific API version
        return create_gemini_client(api_key, model_name)
    except Exception as e:
        print(f"\n====== ERROR: API CLIENT INITIALIZATION FAILED ======")
        print(f"Error details: {str(e)}")
        print("\nPossible causes:")
        print("1. API key validation failed")
        print("2. API configuration error")
        print("3. Client creation error")
        print("\nThe server will now exit. Press any key to close this window...")
        sys.exit(1)

def setup_api_environment():
    """
    Set up the complete API environment including status printing.
    """
    try:
        print_api_status()
        # Initialize API configuration without creating a client
        from .api_key_manager import get_api_key, validate_api_key
        from .api_initialization import print_api_initialization
        from .gemini_config import configure_gemini_api

        api_key = get_api_key()
        if not validate_api_key(api_key):
            print("\n====== ERROR: NO USABLE GEMINI API KEY ======")
            print("This project ships without a key on purpose.")
            print("\nGet one at https://aistudio.google.com/apikey, then either:")
            print("  - set the GEMINI_API_KEY environment variable, or")
            print("  - put GEMINI_API_KEY=... in .env.local at the project root, or")
            print("  - paste it into the app's Gemini settings panel")
            print("\nThe server will now exit.")
            sys.exit(1)

        print_api_initialization(api_key)
        configure_gemini_api(api_key)
    except Exception as e:
        print(f"\n====== ERROR: API ENVIRONMENT SETUP FAILED ======")
        print(f"Error details: {str(e)}")
        print("\nThe server will now exit. Press any key to close this window...")
        sys.exit(1) 