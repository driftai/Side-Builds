import re
import json
from main_server_files.api_configuration.gemini_config import MAIN_MODEL, get_allowed_models_list, validate_model

# Keys whose values must never reach the log. The config dump below is printed
# verbatim for every connection, and a client that supplies its own key was
# having it written to disk in plaintext on every session.
_SECRET_KEYS = {"apikey", "api_key", "authorization", "token", "access_token"}


def _redacted(value):
    """Deep copy of a config with any secret-looking values masked."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if isinstance(k, str) and k.lower() in _SECRET_KEYS:
                out[k] = f"<redacted len={len(v)}>" if isinstance(v, str) and v else v
            else:
                out[k] = _redacted(v)
        return out
    if isinstance(value, list):
        return [_redacted(v) for v in value]
    return value

def extract_voice_configuration(config_data):
    """
    Extracts voice configuration from the provided config data.
    Returns the voice name and any additional voice settings.
    """
    voice_name = None
    try:
        print("Extracting voice configuration...")
        print(f"Config data: {json.dumps(_redacted(config_data), indent=2)}")
        
        # Check for voice in different possible locations in the config
        if "setup" in config_data:
            # First, try to extract from the setup.contents text
            try:
                setup_text = config_data.get("setup", {}).get("contents", [{}])[0].get("parts", [{}])[0].get("text", "")
                if "voice of" in setup_text:
                    # Extract voice name from text like "You are a helpful AI assistant speaking with the voice of Puck."
                    voice_match = re.search(r"voice of (\w+)", setup_text)
                    if voice_match:
                        voice_name = voice_match.group(1)
                        print(f"Extracted voice name from setup text: {voice_name}")
            except Exception as e:
                print(f"Error extracting voice from setup text: {e}")
            
            # If not found in text, check in the standard location
            if not voice_name:
                voice_config = config_data.get("setup", {}).get("speechConfig", {}).get("voiceConfig", {})
                voice_name = voice_config.get("prebuiltVoiceConfig", {}).get("voiceName")
                print(f"Found voice in setup.speechConfig.voiceConfig: {voice_name}")
            
            # If not found in the expected location, check if it's directly in setup
            if not voice_name and "speechConfig" in config_data.get("setup", {}):
                voice_name = config_data.get("setup", {}).get("speechConfig")
                print(f"Found voice directly in setup.speechConfig: {voice_name}")
        elif "speechConfig" in config_data:
            voice_name = config_data.get("speechConfig")
            print(f"Found voice in speechConfig: {voice_name}")
        elif "voice" in config_data:
            voice_name = config_data.get("voice")
            print(f"Found voice in voice field: {voice_name}")
        
        # If we still don't have a voice name, check if it's directly in the config
        if not voice_name and isinstance(config_data, str):
            voice_name = config_data
            print(f"Using config data directly as voice: {voice_name}")
            
        if voice_name:
            print(f"Using voice: {voice_name}")
        else:
            voice_name = "Aoede"
            print(f"No voice name found in config, using default: {voice_name}")
            
        return voice_name

    except Exception as e:
        voice_name = "Aoede"
        print(f"Error extracting voice name: {e}, using default: {voice_name}")
        return voice_name

def extract_model_configuration(config_data):
    """
    Extracts model configuration from the provided config data.
    Returns the model name and override flag.

    Args:
        config_data (dict): The configuration data from the client

    Returns:
        tuple: (model_name, allow_override) where model_name is the requested model and allow_override indicates if client wants to override server default
    """
    try:
        print("Extracting model configuration...")

        # Default values
        model_name = None
        allow_override = False

        # Check for model override flag first
        if "allowModelOverride" in config_data:
            allow_override = bool(config_data.get("allowModelOverride", False))
            print(f"Client model override flag: {allow_override}")

        # Check for model specification
        if "model" in config_data:
            requested_model = config_data.get("model")
            print(f"Client requested model: {requested_model}")

            # Validate the requested model if override is enabled
            if allow_override:
                is_valid = validate_model(requested_model, allow_override=True)
                contains_25 = "2.5" in requested_model.lower()
                starts_with_gemini = requested_model.lower().startswith("gemini")

                if is_valid or (contains_25 and starts_with_gemini):
                    # If it's a custom Gemini 2.5 model name, map it to an actual model
                    if not is_valid and contains_25 and starts_with_gemini:
                        # Map custom names to actual models
                        if "native-audio" in requested_model.lower():
                            model_name = "gemini-2.5-flash-native-audio-preview-09-2025"
                        elif "live" in requested_model.lower():
                            model_name = "gemini-2.5-flash-live-preview"
                        else:
                            model_name = "gemini-2.5-flash-live-preview"  # Default fallback
                        print(f"Mapping custom model '{requested_model}' to actual model '{model_name}'")
                    else:
                        model_name = requested_model
                        print(f"Using client-specified model: {model_name}")
                else:
                    print(f"Client requested invalid model '{requested_model}'. Valid models: {get_allowed_models_list()}")
                    print(f"Falling back to server default model: {MAIN_MODEL}")
                    model_name = MAIN_MODEL
                    allow_override = False  # Don't allow override for invalid models
            else:
                print(f"Model override not enabled, using server default: {MAIN_MODEL}")
                model_name = MAIN_MODEL

        if not model_name:
            model_name = MAIN_MODEL
            allow_override = False
            print(f"No model specified, using server default: {model_name}")

        return model_name, allow_override

    except Exception as e:
        print(f"Error extracting model configuration: {e}, using defaults")
        return MAIN_MODEL, False

def extract_voice_and_model_configuration(config_data):
    """
    Extracts both voice and model configuration from the provided config data.

    Args:
        config_data (dict): The configuration data from the client

    Returns:
        dict: Dictionary containing voice_name, model_name, and allow_override flag
    """
    voice_name = extract_voice_configuration(config_data)
    model_name, allow_override = extract_model_configuration(config_data)

    return {
        "voice_name": voice_name,
        "model_name": model_name,
        "allow_override": allow_override
    }

async def change_voice_settings(new_voice):
    """
    Changes the voice settings for the current session.
    
    Args:
        new_voice (str): The name of the new voice to use
        
    Returns:
        bool: True if the voice was changed successfully
    """
    try:
        print(f"Changing voice settings to: {new_voice}")
        # Here you would typically update any global voice settings
        # or notify other components about the voice change
        
        # For now, we just validate the voice name
        valid_voices = ["Aoede", "Charon", "Fenrir", "Kore", "Leda", "Orus", "Puck", "Zephyr"]
        if new_voice not in valid_voices:
            raise ValueError(f"Invalid voice name. Must be one of: {', '.join(valid_voices)}")
            
        # In a real implementation, you might:
        # 1. Update a global voice configuration
        # 2. Notify any active TTS services
        # 3. Update any relevant configuration files
        
        return True
    except Exception as e:
        print(f"Error changing voice settings: {e}")
        raise 