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
        current_audio_size = len(self.audio_processor.audio_data)
        self.audio_completion_threshold = self._completion_silence_threshold()
        self._log_audio_progress(current_audio_size, prefix=progress_prefix)
        return current_audio_size

    async def _check_short_audio_completion(self, audio_size, direct=False):
        if not self._should_check_completion_immediately(audio_size):
            return False

        label = "Direct chunk: Ultra-short" if direct else "Ultra-short"
        print(
            f"{label} sentence detected ({audio_size} bytes) - checking "
            "completion immediately"
        )
        try:
            completed = await self.check_audio_completion()
            if completed:
                direct_label = " direct chunk" if direct else " sentence"
                print(
                    "Immediate completion triggered for ultra-short"
                    f"{direct_label} ({audio_size} bytes)"
                )
                return True
        except Exception as error:
            suffix = " for direct chunk" if direct else ""
            print(f"Error in immediate completion check{suffix}: {error}")
        return False

    def _schedule_tiny_audio_completion(self, audio_size, direct=False):
        if not self._should_force_completion_aggressively(audio_size):
            return

        prefix = "Direct chunk: " if direct else ""
        print(
            f"{prefix}Tiny audio chunk detected ({audio_size} bytes) - "
            "scheduling aggressive completion"
        )
        scheduled_seq = self._turn_seq
        delay = 0.05 if direct else 0.10

        async def aggressive_completion():
            await asyncio.sleep(delay)
            try:
                if not self._turn_still_current(scheduled_seq):
                    return
                if self.last_audio_time is not None:
                    silence_duration = time.time() - self.last_audio_time
                    if silence_duration > delay:
                        direct_label = " direct" if direct else ""
                        print(
                            f"Force-completing tiny{direct_label} chunk "
                            f"({audio_size} bytes) after "
                            f"{silence_duration:.2f}s silence"
                        )
                        await self.handle_turn_complete()
            except Exception as error:
                suffix = " for direct chunk" if direct else ""
                print(f"Error in aggressive completion{suffix}: {error}")

        asyncio.create_task(aggressive_completion())

    def _schedule_large_audio_completion(self, audio_size, direct=False):
        if not self._should_force_large_completion_fast(audio_size):
            return

        prefix = "Direct chunk: " if direct else ""
        print(
            f"{prefix}Very large audio chunk detected ({audio_size} bytes) - "
            "scheduling fast completion"
        )
        scheduled_seq = self._turn_seq

        async def fast_large_completion():
            if audio_size > 500000:
                await asyncio.sleep(4.0 if direct else 5.0)
                silence_threshold = self.FORCE_COMPLETE_SILENCE_SECONDS
            else:
                await asyncio.sleep(0.15 if direct else 0.20)
                silence_threshold = (
                    self.FORCE_COMPLETE_SILENCE_SECONDS if direct else 240.0
                )

            try:
                if not self._turn_still_current(scheduled_seq):
                    return
                if self.last_audio_time is not None:
                    silence_duration = time.time() - self.last_audio_time
                    if silence_duration > silence_threshold:
                        category = self._describe_audio(audio_size)
                        direct_label = " direct" if direct else ""
                        print(
                            f"Fast force-completing {category}{direct_label} "
                            f"chunk ({audio_size} bytes) after "
                            f"{silence_duration:.2f}s silence"
                        )
                        await self.handle_turn_complete()
            except Exception as error:
                suffix = " for direct chunk" if direct else ""
                print(f"Error in fast large completion{suffix}: {error}")

        asyncio.create_task(fast_large_completion())

    async def process_audio_response(self, audio_data):
        """Process audio carried by a normal model-turn part."""
        try:
            print(f"Received audio data: {len(audio_data)} bytes")
            if not self.connection_monitor.is_websocket_open():
                print("Connection closed, skipping audio processing")
                return

            current_audio_size = self._buffer_audio_chunk(audio_data)
            await self.audio_processor.process_audio_data(
                audio_data, self.audio_processor.is_sequential
            )

            if await self._check_short_audio_completion(current_audio_size):
                return
            self._schedule_tiny_audio_completion(current_audio_size)
            self._schedule_large_audio_completion(current_audio_size)
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

            self.last_audio_time = time.time()
            current_audio_size = self._buffer_audio_chunk(
                audio_data, progress_prefix="Direct chunk: "
            )

            # Keep the legacy keyword contract at this call site unchanged.
            await self.audio_processor.process_audio_data(
                audio_data, sequential=False
            )

            if await self._check_short_audio_completion(
                current_audio_size, direct=True
            ):
                return
            self._schedule_tiny_audio_completion(
                current_audio_size, direct=True
            )
            self._schedule_large_audio_completion(
                current_audio_size, direct=True
            )
            self.connection_monitor.record_activity()
        except Exception as error:
            print(f"Error processing direct audio chunk: {error}")
