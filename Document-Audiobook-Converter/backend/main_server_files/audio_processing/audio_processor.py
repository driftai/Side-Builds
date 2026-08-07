"""Stable ``AudioProcessor`` facade over focused audio responsibilities."""

import asyncio
import base64
import hashlib
import json
import time

import websockets
from google import genai

from .audio_transcription import (
    is_duplicate_transcription as _is_duplicate_transcription,
    process_turn_complete as _process_turn_complete,
)
from .audio_transport import (
    process_audio_data as _process_audio_data,
    process_chunked_audio as _process_chunked_audio,
    safe_send as _safe_send,
    send_session_audio as _send_session_audio,
)
from .sequential_audio_buffer import (
    process_audio_queue as _process_audio_queue,
)
from main_server_files.transcription.transcription_handler import transcribe_audio
from main_server_files.server_initialization.server_config import (
    TRANSCRIBE_GENERATED_AUDIO,
    TRANSCRIBE_WHEN_SESSION_SILENT,
)


SEQUENTIAL_DELAY = 0.08
RETRY_DELAY = 0.02
QUEUE_TIMEOUT = 8.0
MAX_CHUNK_SIZE = 16384
STREAM_TIMEOUT = 3.0


class AudioProcessor:
    """Own audio state while delegating transport, queueing, and finalization."""

    def __init__(
        self,
        websocket,
        connection_id,
        client=None,
        update_activity_callback=None,
    ):
        self.websocket = websocket
        self.connection_id = connection_id
        self.audio_data = b''
        self.spoken_text = ''
        self.audio_queue = asyncio.Queue()
        self.is_sequential = False
        self.is_playing_audio = False
        self.client = client
        self.update_activity_callback = update_activity_callback
        self.last_transcription_hash = None
        self.last_transcription_time = 0
        self.transcription_cooldown = 1.0
        self.audio_playback_lock = asyncio.Lock()
        self.current_audio_task = None
        self.audio_completion_event = asyncio.Event()
        self.audio_session_id = 0

    def reset(self):
        """Reset the audio processor state."""
        self.audio_data = b''
        self.spoken_text = ''
        self.is_playing_audio = False
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
                self.audio_queue.task_done()
            except asyncio.QueueEmpty:
                break
        self.last_transcription_hash = None
        self.last_transcription_time = 0
        self.audio_completion_event.clear()
        if self.current_audio_task and not self.current_audio_task.done():
            self.current_audio_task.cancel()

    def _is_duplicate_transcription(self, transcription_text):
        """Check whether this text duplicates a recently sent transcript."""
        return _is_duplicate_transcription(self, transcription_text)

    async def safe_send(self, message):
        """Safely send a websocket message with timeout protection."""
        return await _safe_send(self, message, STREAM_TIMEOUT)

    async def process_audio_queue(self):
        """Process sequential audio chunks in their established order."""
        return await _process_audio_queue(self, RETRY_DELAY)

    async def _send_session_audio(self, chunks, session_id):
        """Send all chunks for one sequential session."""
        return await _send_session_audio(
            self,
            chunks,
            session_id,
            RETRY_DELAY,
            SEQUENTIAL_DELAY,
        )

    async def process_audio_data(self, audio_data, is_sequential=None):
        """Route incoming audio through sequential or direct transport."""
        return await _process_audio_data(
            self,
            audio_data,
            is_sequential,
            MAX_CHUNK_SIZE,
            RETRY_DELAY,
        )

    async def _process_chunked_audio(
        self,
        audio_data,
        is_sequential,
        session_id,
    ):
        """Split large audio data into ordered transport chunks."""
        return await _process_chunked_audio(
            self,
            audio_data,
            is_sequential,
            session_id,
            MAX_CHUNK_SIZE,
            RETRY_DELAY,
        )

    async def process_turn_complete(self):
        """Finalize and report the current turn's buffered audio."""
        return await _process_turn_complete(
            self,
            QUEUE_TIMEOUT,
            RETRY_DELAY,
            TRANSCRIBE_GENERATED_AUDIO,
            TRANSCRIBE_WHEN_SESSION_SILENT,
            transcribe_audio,
        )
