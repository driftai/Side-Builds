import json
import base64
import io
import wave
from pydub import AudioSegment
import google.generativeai as generative
from main_server_files.api_configuration.gemini_config import TRANSCRIPTION_MODEL, TRANSCRIPTION_CONFIG

async def transcribe_audio(audio_data, client):
    """Transcribe audio data using the Gemini API."""
    try:
        # Check audio size and potentially chunk if too large
        audio_size = len(audio_data) if hasattr(audio_data, '__len__') else 0
        print(f"Transcribing audio: {audio_size} bytes")

        # Gemini has limits on audio file size (typically ~25MB max, but we should be conservative)
        MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10MB limit for safety

        if audio_size > MAX_AUDIO_SIZE:
            print(f"Audio file too large ({audio_size} bytes > {MAX_AUDIO_SIZE} bytes), truncating...")
            # Take the last part of the audio (most recent speech)
            audio_data = audio_data[-MAX_AUDIO_SIZE:]
            print(f"Truncated to {len(audio_data)} bytes")

        # Convert PCM to MP3 first
        mp3_data = await convert_pcm_to_mp3(audio_data)
        if not mp3_data:
            print("Failed to convert PCM to MP3")
            return "[Audio conversion failed]"

        # Check MP3 size after conversion
        mp3_size = len(mp3_data)
        print(f"MP3 data size: {mp3_size} bytes")

        if mp3_size > MAX_AUDIO_SIZE:
            print(f"MP3 file too large ({mp3_size} bytes), cannot transcribe")
            return "[Audio file too large for transcription]"

        # Create a transcription model with specific configuration
        model = generative.GenerativeModel(
            model_name=TRANSCRIPTION_MODEL,
            generation_config=TRANSCRIPTION_CONFIG
        )

        # Create the prompt for transcription (optimized for speed)
        prompt = "Transcribe this audio accurately. Output only the text."

        # Process the transcription
        response = await model.generate_content_async(
            contents=[
                prompt,
                {"mime_type": "audio/mp3", "data": base64.b64encode(mp3_data).decode()}
            ]
        )
        
        # *** ENHANCED ERROR HANDLING: Check for valid response structure ***
        if not response:
            print("No response received from Gemini transcription API")
            return None
            
        # Check if response has parts and is usable
        if hasattr(response, 'parts') and response.parts:
            # Response has parts, check if any have text
            has_text_parts = any(hasattr(part, 'text') and part.text for part in response.parts)
            if not has_text_parts:
                print("Response has parts but no text content")
                return None
        elif hasattr(response, 'text') and response.text:
            # Direct text access works
            pass
        else:
            # Check finish_reason for more context
            finish_reason = getattr(response, 'finish_reason', 'unknown')
            print(f"Invalid Gemini response structure. Finish reason: {finish_reason}")
            
            # Common finish_reason codes and their meanings:
            # 1: FINISH_REASON_STOP (normal completion)
            # 2: FINISH_REASON_MAX_TOKENS
            # 3: FINISH_REASON_SAFETY (content filtered for safety)
            # 4: FINISH_REASON_RECITATION 
            # 8: Often indicates empty/filtered response
            if finish_reason == 3:
                print("Transcription blocked by safety filters")
                return "[Content filtered by safety settings]"
            elif finish_reason == 8:
                print("Gemini returned empty response (possibly due to unclear audio)")
                return "[Audio not clear enough for transcription]"
            else:
                print(f"Unexpected finish_reason: {finish_reason}")
                return "[Transcription unavailable]"
        
        if response and hasattr(response, 'text') and response.text:
            text = response.text
            # Clean up the transcription text
            text = text.replace("[GEMINI: ", "").replace("]", "")
            text = text.replace("P.P.P.P.P.", "").replace("P.P.P.", "").replace("P.P.", "").replace(" P.", "")
            text = text.replace(" P P P P P", "").replace(" P P P", "").replace(" P P", "").replace(" P", "")
            text = text.rstrip(" P").rstrip(".")
            text = text.replace("I.O.D.E.", "Puck")
            text = " ".join(text.split())
            
            # Final validation - ensure we have meaningful content
            if not text.strip() or text.strip() == '<Not recognizable>':
                print("Transcription resulted in empty or unrecognizable content")
                return "[Audio content not recognizable]"
                
            return text
        else:
            print("No transcription result available")
            return None
            
    except Exception as e:
        error_msg = str(e)
        print(f"Error transcribing audio: {error_msg}")

        # Provide meaningful error messages based on error type
        if "400" in error_msg and "invalid argument" in error_msg.lower():
            return "[Audio format issue - transcription unavailable]"
        elif "413" in error_msg or "payload too large" in error_msg.lower():
            return "[Audio file too large - transcription unavailable]"
        elif "429" in error_msg or "quota" in error_msg.lower():
            return "[API quota exceeded - transcription unavailable]"
        elif "timeout" in error_msg.lower() or "deadline" in error_msg.lower():
            return "[Transcription timeout - please try again]"
        else:
            return f"[Transcription error: {error_msg[:50]}...]"

async def convert_pcm_to_mp3(pcm_data, sample_rate=24000, channels=1):
    """Convert PCM audio data to MP3 format."""
    try:
        # Validate input data
        if not pcm_data:
            print("No PCM data provided for conversion")
            return None

        pcm_size = len(pcm_data) if hasattr(pcm_data, '__len__') else 0
        print(f"Converting PCM to MP3: {pcm_size} bytes at {sample_rate}Hz")

        # Create a BytesIO object to hold the WAV data
        wav_buffer = io.BytesIO()

        # Create a WAV file in memory
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)  # 16-bit audio
            wav_file.setframerate(sample_rate)
            # Ensure pcm_data is bytes
            if isinstance(pcm_data, (bytes, bytearray)):
                wav_file.writeframes(pcm_data)
            elif isinstance(pcm_data, io.BytesIO):
                wav_file.writeframes(pcm_data.getvalue())
            else:
                raise ValueError(f"Unsupported audio data type: {type(pcm_data)}")

        # Reset buffer position
        wav_buffer.seek(0)

        # Convert WAV to MP3 using pydub with error handling
        try:
            audio = AudioSegment.from_wav(wav_buffer)
            print(f"Audio loaded successfully: {len(audio)}ms duration")

            # Create a new BytesIO object for the MP3
            mp3_buffer = io.BytesIO()

            # Export with lower bitrate to reduce file size if needed
            audio.export(mp3_buffer, format='mp3', bitrate='128k')

            # Get the MP3 data
            mp3_data = mp3_buffer.getvalue()
            print(f"MP3 conversion successful: {len(mp3_data)} bytes")

            return mp3_data

        except Exception as conversion_error:
            print(f"Audio conversion error: {conversion_error}")
            # Try with different parameters
            try:
                print("Retrying with different conversion parameters...")
                wav_buffer.seek(0)
                audio = AudioSegment.from_wav(wav_buffer)

                mp3_buffer = io.BytesIO()
                # Try with different settings
                audio.export(mp3_buffer, format='mp3', bitrate='64k', parameters=["-ac", "1"])

                mp3_data = mp3_buffer.getvalue()
                print(f"MP3 conversion retry successful: {len(mp3_data)} bytes")
                return mp3_data

            except Exception as retry_error:
                print(f"MP3 conversion retry also failed: {retry_error}")
                return None

    except Exception as e:
        print(f"Error converting PCM to MP3: {e}")
        return None 