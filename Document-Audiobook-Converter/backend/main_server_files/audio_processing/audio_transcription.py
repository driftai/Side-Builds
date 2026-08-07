"""Turn-finalization and transcription helpers for ``AudioProcessor``."""

import asyncio
import base64
import hashlib
import time

from .audio_transport import websocket_is_open


def is_duplicate_transcription(processor, transcription_text):
    """Track the processor's short duplicate-transcription cooldown."""
    if not transcription_text or not transcription_text.strip():
        return False

    if transcription_text.startswith("[") and transcription_text.endswith("]"):
        print("Allowing error message through deduplication filter")
        return False

    current_hash = hashlib.md5(
        transcription_text.strip().encode('utf-8')
    ).hexdigest()
    current_time = time.time()
    if (
        processor.last_transcription_hash == current_hash
        and current_time - processor.last_transcription_time
        < processor.transcription_cooldown
    ):
        print(
            f"Duplicate transcription detected (hash: {current_hash[:8]}), "
            "skipping..."
        )
        return True

    processor.last_transcription_hash = current_hash
    processor.last_transcription_time = current_time
    return False


async def process_turn_complete(
    processor,
    queue_timeout,
    retry_delay,
    transcribe_generated_audio,
    transcribe_when_session_silent,
    transcribe_audio_fn,
):
    """Finalize one buffered turn without changing its established ordering."""
    try:
        print(
            "[DEBUG] Starting process_turn_complete, audio_data exists: "
            f"{processor.audio_data is not None}"
        )
        if processor.audio_data:
            print(
                f"[DEBUG] Audio data size at start: "
                f"{len(processor.audio_data)} bytes"
            )

        if not websocket_is_open(processor.websocket):
            print(
                f"Connection {processor.connection_id} closed, "
                "skipping transcription"
            )
            return None

        audio_data_size = (
            len(processor.audio_data) if processor.audio_data else 0
        )
        print(f"Processing audio data: {audio_data_size} bytes")
        if not processor.audio_data or audio_data_size == 0:
            print("No audio data available for transcription")
            return "[No audio data available]"

        if not processor.audio_queue.empty():
            print(
                "Waiting for audio queue to be processed, remaining items: "
                f"{processor.audio_queue.qsize()}"
            )
            try:
                await asyncio.wait_for(
                    processor.audio_queue.join(), timeout=queue_timeout
                )
                print("Audio queue processing completed")
            except asyncio.TimeoutError:
                print("Timeout waiting for audio queue to be processed")

        current_size = len(processor.audio_data) if processor.audio_data else 0
        print(
            f"[DEBUG] Audio data size before transcription: "
            f"{current_size} bytes"
        )
        if not processor.audio_data or current_size == 0:
            print("Audio data was cleared before transcription")
            return "[Audio data cleared before transcription]"

        if transcribe_generated_audio:
            print(
                f"[DEBUG] Calling transcribe_audio with "
                f"{len(processor.audio_data)} bytes"
            )
            transcribed_text = await transcribe_audio_fn(
                processor.audio_data, processor.client
            )
        else:
            print(
                "[DEBUG] Transcription disabled, skipping API call for "
                f"{len(processor.audio_data)} bytes"
            )
            transcribed_text = None

        if processor.audio_data and websocket_is_open(processor.websocket):
            if not transcribe_generated_audio:
                message_text = processor.spoken_text.strip()
                is_error = False

                if not message_text and transcribe_when_session_silent:
                    print(
                        "Session reported no transcript; transcribing the "
                        "audio instead"
                    )
                    recovered = await transcribe_audio_fn(
                        processor.audio_data, processor.client
                    )
                    if recovered:
                        message_text = recovered.replace(
                            "GEMINI: ", ""
                        ).strip()
            elif transcribed_text:
                cleaned_text = transcribed_text.replace("GEMINI: ", "")
                print(f"Transcribed text: {cleaned_text[:50]}...")
                if processor._is_duplicate_transcription(cleaned_text):
                    print(
                        "Skipping duplicate transcription: "
                        f"{cleaned_text[:30]}..."
                    )
                    return cleaned_text

                message_text = cleaned_text
                is_error = (
                    cleaned_text.startswith("[") and cleaned_text.endswith("]")
                )
            else:
                message_text = (
                    "[Speech detected but transcription unavailable]"
                )
                is_error = True
                print("No transcription result, sending generic message")

            audio_base64 = base64.b64encode(
                processor.audio_data
            ).decode('utf-8')
            for attempt in range(2):
                if websocket_is_open(processor.websocket):
                    send_success = await processor.safe_send({
                        "text": message_text,
                        "is_transcription": True,
                        "is_error": is_error,
                        "audio_data": audio_base64,
                        "audio_format": "audio/pcm;rate=24000",
                    })
                    if send_success:
                        print(
                            "Transcription sent to client "
                            f"(attempt {attempt + 1})"
                        )
                        break
                    print(
                        "Failed to send transcription "
                        f"(attempt {attempt + 1}), retrying..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    print("WebSocket closed, cannot send transcription")
                    break
            return message_text

        if not processor.audio_data:
            print("No audio data available for transcription")
        else:
            print("WebSocket closed, cannot send transcription")
        return None
    except Exception as error:
        print(f"Error processing transcription: {error}")
        return f"[Transcription error: {str(error)[:50]}...]"
    finally:
        print(
            "Resetting audio processor after transcription (was "
            f"{len(processor.audio_data) if processor.audio_data else 0} bytes)"
        )
        processor.reset()
