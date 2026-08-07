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
        self._idle_completion_task = None
        self._settled_completion_task = None

    def _save_response_history(self, text):
        """Route mixin history writes through this module's stable dependency."""
        save_chat_history(text, is_user=False)

    # Keep the finished turn open briefly for trailing output transcription.
    TRANSCRIPT_SETTLE_SECONDS = 0.35

    def schedule_turn_completion(self):
        """End the turn shortly, so trailing transcription is not cut off."""
        self._cancel_idle_completion()
        self._cancel_settled_completion()
        seq = self._turn_seq

        async def finish_when_settled():
            try:
                await asyncio.sleep(self.TRANSCRIPT_SETTLE_SECONDS)
                if not self._turn_still_current(seq):
                    return
                self._settled_completion_task = None
                await self.handle_turn_complete()
            except asyncio.CancelledError:
                return

        self._settled_completion_task = asyncio.create_task(
            finish_when_settled()
        )

    def _cancel_task(self, attribute):
        """Cancel one owned timer without cancelling the task running it."""
        task = getattr(self, attribute, None)
        setattr(self, attribute, None)
        if (
            task is not None
            and task is not asyncio.current_task()
            and not task.done()
        ):
            task.cancel()

    def _cancel_idle_completion(self):
        self._cancel_task('_idle_completion_task')

    def _cancel_settled_completion(self):
        self._cancel_task('_settled_completion_task')

    def cancel_pending_tasks(self):
        """Release completion timers when the owning connection closes."""
        self._cancel_idle_completion()
        self._cancel_settled_completion()

    def schedule_idle_completion(self):
        """Restart the single hang watchdog after receiving real audio."""
        self._cancel_idle_completion()
        audio_size = len(getattr(self.audio_processor, 'audio_data', b'') or b'')
        if (
            audio_size < self.MIN_MEANINGFUL_AUDIO_BYTES
            or self.last_audio_time is None
        ):
            return

        seq = self._turn_seq

        async def finish_after_idle():
            try:
                while self._turn_still_current(seq):
                    last_audio_time = self.last_audio_time
                    if last_audio_time is None:
                        return
                    remaining = (
                        self._completion_silence_threshold()
                        - (time.time() - last_audio_time)
                    )
                    if remaining > 0:
                        await asyncio.sleep(remaining)
                    if not self._turn_still_current(seq):
                        return
                    if self.last_audio_time != last_audio_time:
                        continue
                    completed = await self.check_audio_completion()
                    if completed:
                        self._idle_completion_task = None
                        return
                    audio_size = len(
                        getattr(self.audio_processor, 'audio_data', b'') or b''
                    )
                    if audio_size < self.MIN_MEANINGFUL_AUDIO_BYTES:
                        self._idle_completion_task = None
                        return
                    # Timer resolution can wake a fraction early. Recompute the
                    # remaining silence rather than dropping the only watchdog.
                    await asyncio.sleep(0)
            except asyncio.CancelledError:
                return

        self._idle_completion_task = asyncio.create_task(finish_after_idle())

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
            self.cancel_pending_tasks()

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
            self.last_audio_time = None
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
                if silence_duration >= threshold:
                    print(
                        "Hang guard: completing turn after "
                        f"{silence_duration:.1f}s of silence with "
                        f"{self._describe_audio(audio_size)} buffered - "
                        "Gemini never sent turn_complete"
                    )
                    await self.handle_turn_complete()
                    return True
                return False

            if silence_duration >= threshold:
                print(
                    f"Hang guard: no audio at all for {silence_duration:.1f}s"
                )
            return False
        except Exception as error:
            print(f"Error in audio completion check: {error}")
            return False
