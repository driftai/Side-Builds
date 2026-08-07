"""Response text/audio ingestion shared by ``GeminiResponseHandler``."""

import asyncio
import json
import time


MAX_AUDIO_BUFFER_SIZE = 1024 * 1024 * 10


class ResponseAudioMixin:
    """Keep response ingestion separate from turn-completion state."""

    async def process_response_part(self, part):
        """Process a single part of the Gemini response."""
        if not self.connection_monitor.is_websocket_open():
            print("Connection closed during part processing")
            return

        try:
            if hasattr(part, 'text') and part.text is not None:
                await self.process_text_response(part.text)
                self._save_response_history(part.text)
            elif hasattr(part, 'inline_data') and part.inline_data is not None:
                self.last_audio_time = time.time()
                await self.process_audio_response(part.inline_data.data)
            self.connection_monitor.record_activity()
        except Exception as error:
            print(f"Error processing response part: {error}")

    async def process_text_response(self, text):
        """Process text response from Gemini."""
        try:
            if self.connection_monitor.is_websocket_open():
                await self.connection_monitor.safe_send(json.dumps({"text": text}))
                await asyncio.sleep(0.001)
        except Exception as error:
            print(f"Error sending text response: {error}")

    def _buffer_audio_chunk(self, audio_data, progress_prefix=""):
        """Append one PCM chunk and update shared completion bookkeeping."""
        if (
            len(self.audio_processor.audio_data) + len(audio_data)
            > MAX_AUDIO_BUFFER_SIZE
        ):
            print(
                "Audio buffer would exceed size limit "
                f"({MAX_AUDIO_BUFFER_SIZE} bytes), resetting..."
            )
            self.audio_processor.reset()

        self.audio_processor.audio_data += audio_data
        self.last_audio_time = time.time()
        current_audio_size = len(self.audio_processor.audio_data)
        self.audio_completion_threshold = self._completion_silence_threshold()
        self._log_audio_progress(current_audio_size, prefix=progress_prefix)
        return current_audio_size

    async def process_audio_response(self, audio_data):
        """Process audio carried by a normal model-turn part."""
        try:
            print(f"Received audio data: {len(audio_data)} bytes")
            if not self.connection_monitor.is_websocket_open():
                print("Connection closed, skipping audio processing")
                return

            self._buffer_audio_chunk(audio_data)
            await self.audio_processor.process_audio_data(
                audio_data, self.audio_processor.is_sequential
            )
            self.schedule_idle_completion()
            await asyncio.sleep(0.005)
        except Exception as error:
            print(f"Error processing audio data: {error}")
            self.audio_processor.reset()

    async def process_audio_chunk(self, audio_data):
        """Process direct audio when a Gemini frame has no model turn."""
        try:
            print(f"Processing direct audio chunk: {len(audio_data)} bytes")
            if not self.connection_monitor.is_websocket_open():
                print("Connection closed, skipping direct audio chunk processing")
                return

            self._buffer_audio_chunk(
                audio_data, progress_prefix="Direct chunk: "
            )

            # Keep the legacy keyword contract at this call site unchanged.
            await self.audio_processor.process_audio_data(
                audio_data, sequential=False
            )

            self.schedule_idle_completion()
            self.connection_monitor.record_activity()
        except Exception as error:
            print(f"Error processing direct audio chunk: {error}")
