"""Transcribe generated narration when the session did not report it itself.

The Live session normally says what it spoke alongside the audio, for free. It
does not always: roughly one passage in three comes back with nothing, which
leaves that clip's marker unable to judge whether the narration matched the
source. This fills only those gaps - it is never used for a passage the session
already reported, so it costs one call on the shortfall rather than doubling
every passage, which is what got the old path switched off.

Two things changed from that old path:

  * the model. It was pinned to gemini-2.0-flash, which answers 429 quota
    exhausted on this key - so the feature could not have worked whatever else
    was fixed. Measured 2026-08-07: 2.0-flash refused, 2.5-flash answered.
  * the encoding. It converted PCM to MP3 through pydub, which needs ffmpeg on
    the machine. The API accepts audio/wav, and a WAV header is 44 bytes of
    stdlib, so the dependency bought nothing.
"""
import asyncio
import io
import wave

from main_server_files.api_configuration.gemini_config import (
    TRANSCRIPTION_MODEL,
    TRANSCRIPTION_CONFIG,
)

# What the Live API returns: 24kHz, 16-bit, mono.
PCM_SAMPLE_RATE = 24000
PCM_SAMPLE_WIDTH = 2
PCM_CHANNELS = 1

# Inline request bodies are capped at 20MB total. Well beyond any single
# passage, but a runaway turn should fail cheaply rather than be sent.
MAX_AUDIO_BYTES = 15 * 1024 * 1024

# Milliseconds. Comfortably above what a passage takes, and above the API's own
# ten second floor for a manually set deadline.
REQUEST_TIMEOUT_MS = 30_000

TRANSCRIPTION_PROMPT = (
    "Transcribe this narration exactly as spoken. "
    "Output only the words, with no commentary, labels or quotation marks."
)


def pcm_to_wav(pcm_data: bytes) -> bytes:
    """Wrap raw PCM in a WAV container, which the API accepts and PCM is not."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(PCM_CHANNELS)
        wav.setsampwidth(PCM_SAMPLE_WIDTH)
        wav.setframerate(PCM_SAMPLE_RATE)
        wav.writeframes(pcm_data)
    return buffer.getvalue()


async def transcribe_audio(audio_data, client):
    """Transcribe generated PCM. Returns the text, or None if it could not be."""
    if not audio_data:
        return None

    size = len(audio_data)
    if size > MAX_AUDIO_BYTES:
        print(f"Transcription skipped: {size} bytes is over the inline limit")
        return None

    if client is None:
        print("Transcription skipped: no API client for this session")
        return None

    try:
        wav_data = pcm_to_wav(audio_data)
        print(f"Transcribing {size / 48000:.1f}s of narration with {TRANSCRIPTION_MODEL}")

        # The SDK call is blocking; keep it off the event loop so audio for other
        # passages keeps flowing while this runs.
        def request():
            return client.models.generate_content(
                model=TRANSCRIPTION_MODEL,
                contents=[
                    TRANSCRIPTION_PROMPT,
                    {"inline_data": {"mime_type": "audio/wav", "data": wav_data}},
                ],
                # The client this borrows is the one driving the Live session,
                # which sets a one second deadline suited to streaming. The API
                # rejects that outright here ("minimum allowed deadline is 10s"),
                # so this request carries its own.
                config={**TRANSCRIPTION_CONFIG, "http_options": {"timeout": REQUEST_TIMEOUT_MS}},
            )

        response = await asyncio.to_thread(request)
        text = (getattr(response, "text", None) or "").strip()
        if not text:
            print("Transcription returned nothing")
            return None

        print(f"Transcribed {len(text)} chars: {text[:60]}...")
        return text

    except Exception as error:
        # Never fatal: a passage without a transcript is marked as such, which is
        # better than failing the turn that produced perfectly good audio.
        print(f"Transcription failed ({type(error).__name__}): {str(error)[:140]}")
        return None
