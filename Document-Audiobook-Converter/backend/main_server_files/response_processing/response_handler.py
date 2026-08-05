import json
import asyncio
import websockets
import time
from ..chat_history.chat_history_handler import save_chat_history
from ..transcription.transcription_handler import transcribe_audio

# Maximum audio buffer size (10MB for super-long sentences)
MAX_AUDIO_BUFFER_SIZE = 1024 * 1024 * 10

class GeminiResponseHandler:
    # How long the audio stream must be silent before a deferred task is allowed
    # to declare a turn finished on its own.
    #
    # This was effectively 1.5-2s. Gemini pauses that long between phrases while
    # narrating a long passage, so the heuristic routinely fired *before* the
    # real server_content.turn_complete: it flushed the audio early, and Gemini's
    # genuine turn_complete then arrived during the next request and completed it
    # with 0 bytes. Every following sentence stayed offset by one turn, which is
    # what paused playback on a real PDF. Google's own turn_complete is the
    # authority; this only exists so a genuinely stuck turn cannot hang forever,
    # and the receive loop's 75s response timeout backs it up.
    FORCE_COMPLETE_SILENCE_SECONDS = 20.0

    def __init__(self, connection_monitor, audio_processor):
        self.connection_monitor = connection_monitor
        self.audio_processor = audio_processor
        self.last_audio_time = None
        # A turn ends when Gemini says it ends. This is only the hang guard.
        self.audio_completion_threshold = self.FORCE_COMPLETE_SILENCE_SECONDS
        # Add completion tracking to prevent duplicate turn completions
        self.last_completion_time = 0
        self.completion_cooldown = 0.01  # 0.01 second cooldown between turn completions for continuous playback
        self.pending_completion = False

        # Identifies the turn currently being received. The deferred completion
        # tasks below are fire-and-forget: when a turn finished on its own they
        # were left scheduled and fired into the *next* turn, flushing a
        # turn-complete with 0 bytes. The client then saw an end-of-turn with no
        # audio ("No audio chunks were received before transcription") and the
        # sentence failed. Each deferred task captures this value and does
        # nothing if the turn has moved on since it was scheduled.
        self._turn_seq = 0

    def _turn_still_current(self, seq):
        """True if the turn a deferred task was scheduled for is still active."""
        return self._turn_seq == seq

    def _can_complete_turn(self):
        """Check if we can complete a turn (not too recent and not already pending)."""
        current_time = time.time()

        # Check cooldown period
        if current_time - self.last_completion_time < self.completion_cooldown:
            print(f"Turn completion blocked by cooldown ({current_time - self.last_completion_time:.1f}s < {self.completion_cooldown}s)")
            return False

        # Check if already pending
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
        """Silence required before completing a turn Gemini has not ended itself.

        This replaces a table that picked 0.20s-1.20s based on how many bytes had
        arrived so far. That was backwards: the amount of audio generated tells
        you nothing about whether the model has finished speaking, and the
        buckets were short enough that an ordinary pause mid-sentence ended the
        turn early - the reported symptom of long passages being cut off before
        they finished. Size is no longer part of the decision; Gemini's
        server_content.turn_complete is, and this is only a hang guard.
        """
        return self.FORCE_COMPLETE_SILENCE_SECONDS

    def _describe_audio(self, audio_size):
        """Human-readable length for logs (24kHz 16-bit mono => 48000 bytes/sec)."""
        return f"{audio_size / 48000:.1f}s"

    # Gemini streams audio in small frames, so a status line per frame produced
    # thousands of lines and megabytes of log for a few minutes of playback.
    # Report roughly once per second of generated audio instead.
    _PROGRESS_LOG_INTERVAL_BYTES = 48000

    def _log_audio_progress(self, audio_size, prefix=""):
        last = getattr(self, "_last_progress_log_bytes", 0)
        if audio_size < last:  # buffer was reset for a new turn
            last = 0
        if audio_size - last < self._PROGRESS_LOG_INTERVAL_BYTES:
            return
        self._last_progress_log_bytes = audio_size
        print(f"{prefix}Audio so far: {self._describe_audio(audio_size)} "
              f"({audio_size} bytes) - hang guard at {self.audio_completion_threshold:.0f}s")

    # All sizes below are bytes of 24kHz 16-bit mono PCM: 48000 bytes = 1 second.
    #
    # These bounds used to be 500 and 1000 bytes - 0.01s and 0.02s of audio,
    # far below anything audible - so they could never match the "short
    # sentence" case they describe. What they did match was priming frames:
    # gemini-3.1-flash-live-preview opens its stream with a 2-byte frame (one
    # PCM sample), which tripped both heuristics, force-completed the turn
    # 100ms later, and handed the client an end-of-turn with no audio while the
    # real speech was still arriving. That model produced 0.00s through this
    # server while working fine when called directly.
    #
    # Now they describe real utterances: at least 0.1s of audio before a turn
    # can be considered finished at all, and "short" means under half a second.
    # Both callers are still gated on a silence check, so a long utterance that
    # briefly passes through this band while streaming will not complete early.
    MIN_MEANINGFUL_AUDIO_BYTES = 4800    # 0.1s - below this, nothing has been said yet
    SHORT_UTTERANCE_BYTES = 24000        # 0.5s - e.g. "Yes!"
    TINY_UTTERANCE_BYTES = 14400         # 0.3s

    def _should_check_completion_immediately(self, audio_size):
        """Check if we should immediately check for completion (for very short sentences)."""
        return self.MIN_MEANINGFUL_AUDIO_BYTES <= audio_size < self.SHORT_UTTERANCE_BYTES

    def _should_force_completion_aggressively(self, audio_size):
        """Check if we should force completion very aggressively (for tiny audio chunks)."""
        return self.MIN_MEANINGFUL_AUDIO_BYTES <= audio_size < self.TINY_UTTERANCE_BYTES

    def _should_force_large_completion_fast(self, audio_size):
        """Check if we should force completion fast for very large audio chunks."""
        return audio_size > 250000  # > 250KB chunks get fast forced completion

    async def process_response_part(self, part):
        """Process a single part of the Gemini response."""
        if not self.connection_monitor.is_websocket_open():
            print("Connection closed during part processing")
            return

        try:
            if hasattr(part, 'text') and part.text is not None:
                await self.process_text_response(part.text)
                # Save text responses to chat history immediately
                save_chat_history(part.text, is_user=False)
            elif hasattr(part, 'inline_data') and part.inline_data is not None:
                import time
                self.last_audio_time = time.time()  # Track when audio was received
                await self.process_audio_response(part.inline_data.data)
            # After processing any part, record activity
            self.connection_monitor.record_activity()
        except Exception as e:
            print(f"Error processing response part: {e}")

    async def process_text_response(self, text):
        """Process text response from Gemini."""
        try:
            if self.connection_monitor.is_websocket_open():
                await self.connection_monitor.safe_send(json.dumps({
                    "text": text
                }))
                # Minimal delay for faster text responses
                await asyncio.sleep(0.001)  # Extremely fast text processing
        except Exception as e:
            print(f"Error sending text response: {e}")

    async def process_audio_response(self, audio_data):
        """Process audio response from Gemini with dynamic threshold updates."""
        try:
            print(f"Received audio data: {len(audio_data)} bytes")
            if not self.connection_monitor.is_websocket_open():
                print("Connection closed, skipping audio processing")
                return

            # Check if adding this chunk would exceed the buffer size
            if len(self.audio_processor.audio_data) + len(audio_data) > MAX_AUDIO_BUFFER_SIZE:
                print(f"Audio buffer would exceed size limit ({MAX_AUDIO_BUFFER_SIZE} bytes), resetting...")
                self.audio_processor.reset()

            # Add to audio processor's data
            self.audio_processor.audio_data += audio_data

            # Update completion threshold based on current audio size (dynamic adjustment)
            current_audio_size = len(self.audio_processor.audio_data)
            self.audio_completion_threshold = self._completion_silence_threshold()

            # Log threshold adjustments for monitoring
            self._log_audio_progress(current_audio_size)

            # Process the audio data with minimal delay
            await self.audio_processor.process_audio_data(audio_data, self.audio_processor.is_sequential)

            # For ultra-short sentences, check completion immediately after processing
            if self._should_check_completion_immediately(current_audio_size):
                print(f"Ultra-short sentence detected ({current_audio_size} bytes) - checking completion immediately")
                try:
                    completed = await self.check_audio_completion()
                    if completed:
                        print(f"Immediate completion triggered for ultra-short sentence ({current_audio_size} bytes)")
                        return  # Exit early since we completed the turn
                except Exception as e:
                    print(f"Error in immediate completion check: {e}")

            # For tiny audio chunks, force completion after minimal delay
            if self._should_force_completion_aggressively(current_audio_size):
                print(f"Tiny audio chunk detected ({current_audio_size} bytes) - scheduling aggressive completion")
                # Schedule aggressive completion check after a very short delay
                scheduled_seq = self._turn_seq

                async def aggressive_completion():
                    await asyncio.sleep(0.10)  # Longer delay for tiny chunks
                    try:
                        if not self._turn_still_current(scheduled_seq):
                            return  # That turn already completed; do not touch the next one
                        if self.last_audio_time is not None:
                            import time
                            silence_duration = time.time() - self.last_audio_time
                            if silence_duration > 0.10:  # Require 100ms of silence
                                print(f"Force-completing tiny chunk ({current_audio_size} bytes) after {silence_duration:.2f}s silence")
                                await self.handle_turn_complete()
                    except Exception as e:
                        print(f"Error in aggressive completion: {e}")

                # Don't await this - let it run in background
                asyncio.create_task(aggressive_completion())

            # For very large audio chunks, force fast completion
            if self._should_force_large_completion_fast(current_audio_size):
                print(f"Very large audio chunk detected ({current_audio_size} bytes) - scheduling fast completion")
                # Schedule fast completion check for large chunks
                scheduled_seq = self._turn_seq

                async def fast_large_completion():
                    # More patient delay for very large chunks
                    if current_audio_size > 500000:  # Super large chunks get much more time
                        await asyncio.sleep(5.0)  # Much longer delay for super-large chunks
                        silence_threshold = self.FORCE_COMPLETE_SILENCE_SECONDS
                    else:
                        await asyncio.sleep(0.20)  # Longer delay for large chunks
                        silence_threshold = 240.0   # Require much more silence for completion

                    try:
                        if not self._turn_still_current(scheduled_seq):
                            return  # That turn already completed; do not touch the next one
                        if self.last_audio_time is not None:
                            import time
                            silence_duration = time.time() - self.last_audio_time
                            if silence_duration > silence_threshold:
                                category = self._describe_audio(current_audio_size)
                                print(f"Fast force-completing {category} chunk ({current_audio_size} bytes) after {silence_duration:.2f}s silence")
                                await self.handle_turn_complete()
                    except Exception as e:
                        print(f"Error in fast large completion: {e}")

                # Don't await this - let it run in background
                asyncio.create_task(fast_large_completion())

            # Minimal delay for faster audio streaming
            await asyncio.sleep(0.005)  # Ultra fast audio processing
        except Exception as e:
            print(f"Error processing audio data: {e}")
            # Reset audio processor on error
            self.audio_processor.reset()

    async def handle_turn_complete(self):
        """Handle turn completion from Gemini."""
        try:
            # One line per turn, so a passage whose transcript came back short can
            # be spotted in the log without instrumenting the server again.
            print(f"Turn ending with {len(getattr(self.audio_processor, 'spoken_text', ''))} chars "
                  f"of transcript for {self._describe_audio(len(getattr(self.audio_processor, 'audio_data', b'')))} of audio")
            print(f"[DEBUG] handle_turn_complete called, audio_processor exists: {self.audio_processor is not None}")
            if self.audio_processor and self.audio_processor.audio_data:
                print(f"[DEBUG] Audio data size in handle_turn_complete: {len(self.audio_processor.audio_data)} bytes")

            # Check if we can complete this turn
            if not self._can_complete_turn():
                print("Skipping duplicate turn completion")
                return None

            # Mark completion as started. Advancing the sequence here retires any
            # deferred completion task still scheduled for this turn.
            self._mark_completion_started()
            self._turn_seq += 1

            print(f"Processing turn complete with {len(self.audio_processor.audio_data)} bytes of audio data")

            # Check if we have audio data to process
            if not self.audio_processor.audio_data or len(self.audio_processor.audio_data) == 0:
                print("No audio data available for transcription")
                return "[No audio data available]"

            # Process audio data and get transcription
            print(f"[DEBUG] About to call process_turn_complete")
            transcribed_text = await self.audio_processor.process_turn_complete()
            print(f"[DEBUG] process_turn_complete returned: {transcribed_text is not None}")

            if transcribed_text:
                print(f"Got transcription: {transcribed_text[:50]}...")
                # Save to chat history
                save_chat_history(transcribed_text, is_user=False)

            # Minimal delay for faster turn completion
            await asyncio.sleep(0.02)  # Very fast turn completion
            return transcribed_text
        except Exception as e:
            print(f"Error processing transcription: {e}")
            return f"[Transcription error: {str(e)[:50]}...]"
        finally:
            # Mark completion as finished
            self._mark_completion_finished()
            # Only reset audio processor after successful transcription processing
            # Don't reset here as it might interfere with async transcription

    async def process_audio_chunk(self, audio_data):
        """Process a direct audio chunk when model_turn is missing from response with dynamic thresholds."""
        try:
            print(f"Processing direct audio chunk: {len(audio_data)} bytes")
            if not self.connection_monitor.is_websocket_open():
                print("Connection closed, skipping direct audio chunk processing")
                return

            # Update last audio time for completion tracking
            import time
            self.last_audio_time = time.time()

            # Check if adding this chunk would exceed the buffer size
            if len(self.audio_processor.audio_data) + len(audio_data) > MAX_AUDIO_BUFFER_SIZE:
                print(f"Audio buffer would exceed size limit ({MAX_AUDIO_BUFFER_SIZE} bytes), resetting...")
                self.audio_processor.reset()

            # Add to audio processor's data
            self.audio_processor.audio_data += audio_data

            # Update completion threshold based on current audio size (for direct chunks too)
            current_audio_size = len(self.audio_processor.audio_data)
            self.audio_completion_threshold = self._completion_silence_threshold()

            # Log threshold adjustments for direct chunks
            self._log_audio_progress(current_audio_size, prefix="Direct chunk: ")

            # Process the audio data directly (non-sequential for direct chunks)
            await self.audio_processor.process_audio_data(audio_data, sequential=False)

            # For ultra-short direct chunks, check completion immediately
            if self._should_check_completion_immediately(current_audio_size):
                print(f"Direct chunk: Ultra-short sentence detected ({current_audio_size} bytes) - checking completion immediately")
                try:
                    completed = await self.check_audio_completion()
                    if completed:
                        print(f"Immediate completion triggered for ultra-short direct chunk ({current_audio_size} bytes)")
                        return  # Exit early since we completed the turn
                except Exception as e:
                    print(f"Error in immediate completion check for direct chunk: {e}")

            # For tiny direct chunks, force completion after minimal delay
            if self._should_force_completion_aggressively(current_audio_size):
                print(f"Direct chunk: Tiny audio chunk detected ({current_audio_size} bytes) - scheduling aggressive completion")
                # Schedule aggressive completion check after a very short delay
                scheduled_seq = self._turn_seq

                async def aggressive_completion():
                    await asyncio.sleep(0.05)  # Longer delay for direct chunks
                    try:
                        if not self._turn_still_current(scheduled_seq):
                            return  # That turn already completed; do not touch the next one
                        if self.last_audio_time is not None:
                            import time
                            silence_duration = time.time() - self.last_audio_time
                            if silence_duration > 0.05:  # Require 50ms of silence for direct chunks
                                print(f"Force-completing tiny direct chunk ({current_audio_size} bytes) after {silence_duration:.2f}s silence")
                                await self.handle_turn_complete()
                    except Exception as e:
                        print(f"Error in aggressive completion for direct chunk: {e}")

                # Don't await this - let it run in background
                asyncio.create_task(aggressive_completion())

            # For very large direct chunks, force fast completion
            if self._should_force_large_completion_fast(current_audio_size):
                print(f"Direct chunk: Very large audio chunk detected ({current_audio_size} bytes) - scheduling fast completion")
                # Schedule fast completion check for large direct chunks
                scheduled_seq = self._turn_seq

                async def fast_large_completion():
                    # More patient delay for very large direct chunks
                    if current_audio_size > 500000:  # Super large direct chunks get much more time
                        await asyncio.sleep(4.0)  # Much longer delay for super-large direct chunks
                        silence_threshold = self.FORCE_COMPLETE_SILENCE_SECONDS
                    else:
                        await asyncio.sleep(0.15)  # Longer delay for direct chunks
                        silence_threshold = self.FORCE_COMPLETE_SILENCE_SECONDS

                    try:
                        if not self._turn_still_current(scheduled_seq):
                            return  # That turn already completed; do not touch the next one
                        if self.last_audio_time is not None:
                            import time
                            silence_duration = time.time() - self.last_audio_time
                            if silence_duration > silence_threshold:
                                category = self._describe_audio(current_audio_size)
                                print(f"Fast force-completing {category} direct chunk ({current_audio_size} bytes) after {silence_duration:.2f}s silence")
                                await self.handle_turn_complete()
                    except Exception as e:
                        print(f"Error in fast large completion for direct chunk: {e}")

                # Don't await this - let it run in background
                asyncio.create_task(fast_large_completion())

            # Record activity
            self.connection_monitor.record_activity()

        except Exception as e:
            print(f"Error processing direct audio chunk: {e}")
            # Don't reset on error for direct chunks - let the main processor handle it

    async def check_audio_completion(self):
        """Hang guard only: complete a turn Gemini has left open for far too long.

        This used to end a turn after a size-derived 0.20s-1.20s of quiet, which
        is shorter than the pauses Gemini leaves between clauses - so a long
        sentence could be declared finished partway through and the rest of its
        audio discarded. Nothing here infers "the sentence ended" any more; that
        is server_content.turn_complete's job. This only breaks a genuine stall.
        """
        try:
            if not hasattr(self.audio_processor, 'audio_data'):
                return False

            audio_size = len(self.audio_processor.audio_data)
            if self.last_audio_time is None:
                if audio_size > 0:
                    print(f"Receiving audio ({self._describe_audio(audio_size)}) - waiting for Gemini's turn_complete")
                return False

            silence_duration = time.time() - self.last_audio_time
            threshold = self._completion_silence_threshold()

            if audio_size > 0:
                if silence_duration > threshold:
                    print(
                        f"Hang guard: completing turn after {silence_duration:.1f}s of silence "
                        f"with {self._describe_audio(audio_size)} buffered - Gemini never sent turn_complete"
                    )
                    await self.handle_turn_complete()
                    return True
                return False

            # Nothing buffered at all: report a stall, but never complete an
            # empty turn here - that is what desynchronised the stream before.
            if silence_duration > threshold:
                print(f"Hang guard: no audio at all for {silence_duration:.1f}s")
            return False

        except Exception as e:
            print(f"Error in audio completion check: {e}")
            # On error, be conservative and don't complete
            return False

    async def inject_completion_indicator(self, server_content):
        """Inject completion indicators into server_content when they're missing."""
        try:
            # Only inject if we have audio data and no completion indicators
            if hasattr(self.audio_processor, 'audio_data'):
                audio_size = len(self.audio_processor.audio_data)
                if audio_size > 1000:  # Only inject if we have substantial audio data
                    print(f"Injecting completion indicator for {audio_size} bytes of audio data")

                    # Check current completion indicators
                    current_turn_complete = getattr(server_content, 'turn_complete', None)
                    current_final = getattr(server_content, 'final', None)
                    current_finished = getattr(server_content, 'finished', None)
                    current_complete = getattr(server_content, 'complete', None)

                    # If any completion indicator is already True, don't inject
                    if current_turn_complete or current_final or current_finished or current_complete:
                        print(f"Completion indicator already present: turn_complete={current_turn_complete}, final={current_final}, finished={current_finished}, complete={current_complete}")
                        return False

                    # Try to inject turn_complete into server_content
                    try:
                        server_content.turn_complete = True
                        print("Successfully injected turn_complete=True into server_content")
                        return True
                    except (AttributeError, TypeError) as e:
                        # If we can't modify the object, try setting it as an attribute
                        try:
                            setattr(server_content, 'turn_complete', True)
                            print("Successfully set turn_complete=True using setattr")
                            return True
                        except Exception as e2:
                            print(f"Failed to inject completion indicator: {e2}")
                            return False

            return False

        except Exception as e:
            print(f"Error injecting completion indicator: {e}")
            return False
