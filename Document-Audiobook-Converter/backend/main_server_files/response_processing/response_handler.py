"""Turn-completion state and stable Gemini response-handler facade."""

import asyncio
import json
import time

import websockets

from .response_audio_handler import MAX_AUDIO_BUFFER_SIZE, ResponseAudioMixin
from ..chat_history.chat_history_handler import save_chat_history
from ..transcription.transcription_handler import transcribe_audio


class GeminiResponseHandler(ResponseAudioMixin):
    """Coordinate one response turn while ingestion lives in a focused mixin."""

    # Gemini's turn_complete is authoritative; this is only a hang guard.
    FORCE_COMPLETE_SILENCE_SECONDS = 20.0

    def __init__(self, connection_monitor, audio_processor):
        self.connection_monitor = connection_monitor
        self.audio_processor = audio_processor
        self.last_audio_time = None
        self.audio_completion_threshold = self.FORCE_COMPLETE_SILENCE_SECONDS
        self.last_completion_time = 0
        self.completion_cooldown = 0.01
        self.pending_completion = False

        # Fire-and-forget completion tasks capture this sequence and retire when
        # another path has already advanced the turn.
        self._turn_seq = 0

    def _save_response_history(self, text):
        """Route mixin history writes through this module's stable dependency."""
        save_chat_history(text, is_user=False)

    # Keep the finished turn open briefly for trailing output transcription.
    TRANSCRIPT_SETTLE_SECONDS = 0.35

    def schedule_turn_completion(self):
        """End the turn shortly, so trailing transcription is not cut off."""
        seq = self._turn_seq

        async def finish_when_settled():
            await asyncio.sleep(self.TRANSCRIPT_SETTLE_SECONDS)
            if not self._turn_still_current(seq):
                return
            await self.handle_turn_complete()

        asyncio.create_task(finish_when_settled())

    def _turn_still_current(self, seq):
        """True if the turn a deferred task was scheduled for is still active."""
        return self._turn_seq == seq

    def _can_complete_turn(self):
        """Check that completion is neither too recent nor already pending."""
        current_time = time.time()
        if current_time - self.last_completion_time < self.completion_cooldown:
            print(
                "Turn completion blocked by cooldown "
                f"({current_time - self.last_completion_time:.1f}s < "
                f"{self.completion_cooldown}s)"
            )
            return False
        if self.pending_completion:
            print("Turn completion blocked - already pending completion")
            return False
        return True

    def _mark_completion_started(self):
        """Mark that a completion has started."""
        self.last_completion_time = time.time()
        self.pending_completion = True

    def _mark_completion_finished(self):
        """Mark that a completion has finished."""
        self.pending_completion = False

    def _completion_silence_threshold(self):
        """Return the silence duration used only to break a stuck turn."""
        return self.FORCE_COMPLETE_SILENCE_SECONDS

    def _describe_audio(self, audio_size):
        """Describe 24kHz 16-bit mono PCM length for logs."""
        return f"{audio_size / 48000:.1f}s"

    _PROGRESS_LOG_INTERVAL_BYTES = 48000

    def _log_audio_progress(self, audio_size, prefix=""):
        last = getattr(self, "_last_progress_log_bytes", 0)
        if audio_size < last:
            last = 0
        if audio_size - last < self._PROGRESS_LOG_INTERVAL_BYTES:
            return
        self._last_progress_log_bytes = audio_size
        print(
            f"{prefix}Audio so far: {self._describe_audio(audio_size)} "
            f"({audio_size} bytes) - hang guard at "
            f"{self.audio_completion_threshold:.0f}s"
        )

    # 24kHz 16-bit mono PCM: 48000 bytes = one second.
    MIN_MEANINGFUL_AUDIO_BYTES = 4800
    SHORT_UTTERANCE_BYTES = 24000
    TINY_UTTERANCE_BYTES = 14400

    def _should_check_completion_immediately(self, audio_size):
        """Whether a short real utterance should run the hang check now."""
        return (
            self.MIN_MEANINGFUL_AUDIO_BYTES
            <= audio_size
            < self.SHORT_UTTERANCE_BYTES
        )

    def _should_force_completion_aggressively(self, audio_size):
        """Whether a tiny utterance should schedule the legacy short check."""
        return (
            self.MIN_MEANINGFUL_AUDIO_BYTES
            <= audio_size
            < self.TINY_UTTERANCE_BYTES
        )

    def _should_force_large_completion_fast(self, audio_size):
        """Whether a large buffer should schedule the legacy large check."""
        return audio_size > 250000

    async def handle_turn_complete(self):
        """Handle turn completion from Gemini."""
        try:
            print(
                "Turn ending with "
                f"{len(getattr(self.audio_processor, 'spoken_text', ''))} "
                "chars of transcript for "
                f"{self._describe_audio(len(getattr(self.audio_processor, 'audio_data', b'')))} "
                "of audio"
            )
            print(
                "[DEBUG] handle_turn_complete called, audio_processor exists: "
                f"{self.audio_processor is not None}"
            )
            if self.audio_processor and self.audio_processor.audio_data:
                print(
                    "[DEBUG] Audio data size in handle_turn_complete: "
                    f"{len(self.audio_processor.audio_data)} bytes"
                )

            if not self._can_complete_turn():
                print("Skipping duplicate turn completion")
                return None

            self._mark_completion_started()
            self._turn_seq += 1

            print(
                "Processing turn complete with "
                f"{len(self.audio_processor.audio_data)} bytes of audio data"
            )
            if (
                not self.audio_processor.audio_data
                or len(self.audio_processor.audio_data) == 0
            ):
                print("No audio data available for transcription")
                return "[No audio data available]"

            print("[DEBUG] About to call process_turn_complete")
            transcribed_text = await self.audio_processor.process_turn_complete()
            print(
                "[DEBUG] process_turn_complete returned: "
                f"{transcribed_text is not None}"
            )

            if transcribed_text:
                print(f"Got transcription: {transcribed_text[:50]}...")
                save_chat_history(transcribed_text, is_user=False)

            await asyncio.sleep(0.02)
            return transcribed_text
        except Exception as error:
            print(f"Error processing transcription: {error}")
            return f"[Transcription error: {str(error)[:50]}...]"
        finally:
            self._mark_completion_finished()

    async def check_audio_completion(self):
        """Complete only a turn Gemini has left open beyond the hang threshold."""
        try:
            if not hasattr(self.audio_processor, 'audio_data'):
                return False

            audio_size = len(self.audio_processor.audio_data)
            if self.last_audio_time is None:
                if audio_size > 0:
                    print(
                        f"Receiving audio ({self._describe_audio(audio_size)}) - "
                        "waiting for Gemini's turn_complete"
                    )
                return False

            silence_duration = time.time() - self.last_audio_time
            threshold = self._completion_silence_threshold()
            if audio_size > 0:
                if silence_duration > threshold:
                    print(
                        "Hang guard: completing turn after "
                        f"{silence_duration:.1f}s of silence with "
                        f"{self._describe_audio(audio_size)} buffered - "
                        "Gemini never sent turn_complete"
                    )
                    await self.handle_turn_complete()
                    return True
                return False

            if silence_duration > threshold:
                print(
                    f"Hang guard: no audio at all for {silence_duration:.1f}s"
                )
            return False
        except Exception as error:
            print(f"Error in audio completion check: {error}")
            return False

    async def inject_completion_indicator(self, server_content):
        """Inject a missing completion indicator when enough audio is buffered."""
        try:
            if hasattr(self.audio_processor, 'audio_data'):
                audio_size = len(self.audio_processor.audio_data)
                if audio_size > 1000:
                    print(
                        "Injecting completion indicator for "
                        f"{audio_size} bytes of audio data"
                    )
                    current_turn_complete = getattr(
                        server_content, 'turn_complete', None
                    )
                    current_final = getattr(server_content, 'final', None)
                    current_finished = getattr(server_content, 'finished', None)
                    current_complete = getattr(server_content, 'complete', None)
                    if (
                        current_turn_complete
                        or current_final
                        or current_finished
                        or current_complete
                    ):
                        print(
                            "Completion indicator already present: "
                            f"turn_complete={current_turn_complete}, "
                            f"final={current_final}, "
                            f"finished={current_finished}, "
                            f"complete={current_complete}"
                        )
                        return False

                    try:
                        server_content.turn_complete = True
                        print(
                            "Successfully injected turn_complete=True into "
                            "server_content"
                        )
                        return True
                    except (AttributeError, TypeError):
                        try:
                            setattr(server_content, 'turn_complete', True)
                            print(
                                "Successfully set turn_complete=True using setattr"
                            )
                            return True
                        except Exception as secondary_error:
                            print(
                                "Failed to inject completion indicator: "
                                f"{secondary_error}"
                            )
                            return False
            return False
        except Exception as error:
            print(f"Error injecting completion indicator: {error}")
            return False
