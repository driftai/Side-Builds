import base64
import asyncio
import json
import websockets
import hashlib
import time
from main_server_files.transcription.transcription_handler import transcribe_audio
from main_server_files.server_initialization.server_config import TRANSCRIBE_GENERATED_AUDIO
from google import genai

# Optimized audio processing settings for stable streaming
SEQUENTIAL_DELAY = 0.08    # Slightly slower sequential processing for stability
RETRY_DELAY = 0.02         # Slightly slower retries to prevent overwhelming connection
QUEUE_TIMEOUT = 8.0        # Longer timeout for better stability
MAX_CHUNK_SIZE = 16384     # Limit audio chunk size to prevent network issues (16KB)
STREAM_TIMEOUT = 3.0       # Timeout for individual audio sends

class AudioProcessor:
    def __init__(self, websocket, connection_id, client=None, update_activity_callback=None):
        self.websocket = websocket
        self.connection_id = connection_id
        self.audio_data = b''
        # The model's own words for the turn being received, accumulated from the
        # session's output transcription and sent with the turn-complete message.
        self.spoken_text = ''
        self.audio_queue = asyncio.Queue()
        self.is_sequential = False
        self.is_playing_audio = False
        self.client = client
        self.update_activity_callback = update_activity_callback
        # Add deduplication tracking
        self.last_transcription_hash = None
        self.last_transcription_time = 0
        self.transcription_cooldown = 1.0  # 1 second cooldown between identical transcriptions
        # Add audio playback management
        self.audio_playback_lock = asyncio.Lock()
        self.current_audio_task = None
        self.audio_completion_event = asyncio.Event()
        self.audio_session_id = 0  # Track audio sessions to prevent overlap

    def reset(self):
        """Reset the audio processor state."""
        self.audio_data = b''
        self.spoken_text = ''
        self.is_playing_audio = False
        # Clear the queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
                self.audio_queue.task_done()
            except asyncio.QueueEmpty:
                break
        # Reset deduplication tracking
        self.last_transcription_hash = None
        self.last_transcription_time = 0
        # Reset audio management
        self.audio_completion_event.clear()
        if self.current_audio_task and not self.current_audio_task.done():
            self.current_audio_task.cancel()

    def _is_duplicate_transcription(self, transcription_text):
        """Check if this transcription is a duplicate of a recently sent one."""
        if not transcription_text or not transcription_text.strip():
            return False

        # Don't deduplicate error messages - always send them
        if transcription_text.startswith("[") and transcription_text.endswith("]"):
            print("Allowing error message through deduplication filter")
            return False

        # Create hash of the transcription text
        current_hash = hashlib.md5(transcription_text.strip().encode('utf-8')).hexdigest()
        current_time = time.time()

        # Check if this is the same as the last transcription
        if (self.last_transcription_hash == current_hash and
            current_time - self.last_transcription_time < self.transcription_cooldown):
            print(f"Duplicate transcription detected (hash: {current_hash[:8]}), skipping...")
            return True

        # Update tracking
        self.last_transcription_hash = current_hash
        self.last_transcription_time = current_time
        return False

    async def safe_send(self, message):
        """Safely send a message through the websocket with timeout protection."""
        try:
            if self.websocket.state not in (websockets.protocol.State.CLOSED, websockets.protocol.State.CLOSING):
                # Add timeout to prevent hanging sends
                await asyncio.wait_for(
                    self.websocket.send(json.dumps(message)),
                    timeout=STREAM_TIMEOUT
                )
                if self.update_activity_callback:
                    self.update_activity_callback()
                return True
            return False
        except asyncio.TimeoutError:
            print(f"Timeout sending message to connection {self.connection_id}")
            return False
        except Exception as e:
            print(f"Error sending message to connection {self.connection_id}: {e}")
            return False

    async def process_audio_queue(self):
        """Process audio chunks in sequential order with session management."""
        current_session = None
        session_chunks = []

        try:
            while True:
                if self.websocket.state in (websockets.protocol.State.CLOSED, websockets.protocol.State.CLOSING):
                    print(f"Connection {self.connection_id} closed, stopping audio queue processing")
                    break

                try:
                    # Get audio data and session info from queue
                    queue_item = await self.audio_queue.get()
                    if isinstance(queue_item, tuple):
                        audio_data, session_id = queue_item
                    else:
                        # Backward compatibility for old format
                        audio_data = queue_item
                        session_id = "legacy"

                    # Check if this is a new session
                    if session_id != current_session:
                        # Complete previous session if it exists
                        if current_session is not None and session_chunks:
                            await self._send_session_audio(session_chunks, current_session)
                            session_chunks = []

                        current_session = session_id
                        print(f"Starting new audio session: {session_id}")

                    # Add chunk to current session
                    session_chunks.append(audio_data)

                    self.audio_queue.task_done()

                except Exception as e:
                    print(f"Error processing audio queue: {e}")
                    await asyncio.sleep(RETRY_DELAY)

        except asyncio.CancelledError:
            print("Audio queue processor cancelled")
            # Send any remaining audio before cancellation
            if session_chunks:
                try:
                    await self._send_session_audio(session_chunks, current_session or "cancelled")
                except Exception as e:
                    print(f"Error sending remaining audio on cancellation: {e}")
        except Exception as e:
            print(f"Error in audio queue processor: {e}")

    async def _send_session_audio(self, chunks, session_id):
        """Send all chunks for a session as a complete audio block."""
        if not chunks:
            return

        try:
            self.is_playing_audio = True
            print(f"Sending audio session {session_id} with {len(chunks)} chunks")

            # Combine all chunks for this session
            combined_audio = b''.join(chunks)
            base64_audio = base64.b64encode(combined_audio).decode('utf-8')

            send_success = False

            # Send the complete session audio
            for attempt in range(3):
                if self.websocket.state not in (websockets.protocol.State.CLOSED, websockets.protocol.State.CLOSING):
                    send_success = await self.safe_send({
                        "audio": base64_audio,
                        "sequential": True,
                        "session_id": session_id,
                        "complete_session": True
                    })
                    if send_success:
                        print(f"Session {session_id} audio sent to client (attempt {attempt+1})")
                        break
                    else:
                        print(f"Failed to send session {session_id} audio (attempt {attempt+1}), retrying...")
                        await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    print(f"WebSocket closed for connection {self.connection_id}, cannot send session {session_id}")
                    break

            # Wait for session completion before allowing next session
            await asyncio.sleep(SEQUENTIAL_DELAY)

        except Exception as e:
            print(f"Error sending session {session_id} audio: {e}")
        finally:
            self.is_playing_audio = False

    async def process_audio_data(self, audio_data, is_sequential=None):
        """Process incoming audio data with session management and optimized streaming."""
        async with self.audio_playback_lock:
            # Increment session ID to track this audio session
            self.audio_session_id += 1
            current_session = self.audio_session_id

            print(f"Starting audio session {current_session} with {len(audio_data)} bytes")

            # Use instance sequential setting if none provided
            if is_sequential is None:
                is_sequential = self.is_sequential

            # Check if audio data needs chunking for better streaming
            if len(audio_data) > MAX_CHUNK_SIZE:
                print(f"Audio data ({len(audio_data)} bytes) exceeds max chunk size ({MAX_CHUNK_SIZE}), chunking...")
                await self._process_chunked_audio(audio_data, is_sequential, current_session)
                return

            if is_sequential:
                await self.audio_queue.put((audio_data, current_session))
                print(f"Added audio chunk to sequential queue, size: {self.audio_queue.qsize()}, session: {current_session}")
            else:
                base64_audio = base64.b64encode(audio_data).decode('utf-8')
                send_success = False

                # Improved retry attempts with better error handling
                for attempt in range(3):  # Increased retries for better reliability
                    if self.websocket.state not in (websockets.protocol.State.CLOSED, websockets.protocol.State.CLOSING):
                        send_success = await self.safe_send({
                            "audio": base64_audio,
                            "sequential": False,
                            "session_id": current_session
                        })
                        if send_success:
                            print(f"Direct audio sent to client (attempt {attempt+1}), session: {current_session}")
                            break
                        else:
                            print(f"Failed to send direct audio (attempt {attempt+1}), retrying...")
                            await asyncio.sleep(RETRY_DELAY * (attempt + 1))  # Exponential backoff
                    else:
                        print(f"WebSocket closed for connection {self.connection_id}, cannot send audio")
                        break

    async def _process_chunked_audio(self, audio_data, is_sequential, session_id):
        """Process large audio data by chunking it into smaller pieces."""
        chunk_size = MAX_CHUNK_SIZE
        total_chunks = (len(audio_data) + chunk_size - 1) // chunk_size

        print(f"Processing {len(audio_data)} bytes in {total_chunks} chunks, session: {session_id}")

        for i in range(total_chunks):
            start_idx = i * chunk_size
            end_idx = min(start_idx + chunk_size, len(audio_data))
            chunk = audio_data[start_idx:end_idx]

            try:
                if is_sequential:
                    await self.audio_queue.put((chunk, session_id))
                    print(f"Added chunk {i+1}/{total_chunks} to sequential queue, session: {session_id}")
                else:
                    base64_chunk = base64.b64encode(chunk).decode('utf-8')
                    send_success = False

                    for attempt in range(2):
                        if self.websocket.state not in (websockets.protocol.State.CLOSED, websockets.protocol.State.CLOSING):
                            send_success = await self.safe_send({
                                "audio": base64_chunk,
                                "sequential": False,
                                "chunk_index": i,
                                "total_chunks": total_chunks,
                                "session_id": session_id
                            })
                            if send_success:
                                print(f"Chunk {i+1}/{total_chunks} sent (attempt {attempt+1}), session: {session_id}")
                                break
                            else:
                                print(f"Failed to send chunk {i+1}/{total_chunks} (attempt {attempt+1}), retrying...")
                                await asyncio.sleep(RETRY_DELAY)
                        else:
                            print(f"WebSocket closed during chunking for connection {self.connection_id}")
                            return

                    if not send_success:
                        print(f"Failed to send chunk {i+1}/{total_chunks} after all retries")
                        break

                # Add small delay between chunks to prevent overwhelming the connection
                await asyncio.sleep(0.01)

            except Exception as e:
                print(f"Error processing chunk {i+1}/{total_chunks}: {e}")
                break

    async def process_turn_complete(self):
        """Process audio data when a turn is complete with optimized performance."""
        try:
            print(f"[DEBUG] Starting process_turn_complete, audio_data exists: {self.audio_data is not None}")
            if self.audio_data:
                print(f"[DEBUG] Audio data size at start: {len(self.audio_data)} bytes")

            if self.websocket.state in (websockets.protocol.State.CLOSED, websockets.protocol.State.CLOSING):
                print(f"Connection {self.connection_id} closed, skipping transcription")
                return None

            # Store audio data length to avoid race conditions
            audio_data_size = len(self.audio_data) if self.audio_data else 0
            print(f"Processing audio data: {audio_data_size} bytes")

            if not self.audio_data or audio_data_size == 0:
                print("No audio data available for transcription")
                return "[No audio data available]"

            if not self.audio_queue.empty():
                print(f"Waiting for audio queue to be processed, remaining items: {self.audio_queue.qsize()}")
                try:
                    # Reduced timeout for faster queue processing
                    await asyncio.wait_for(self.audio_queue.join(), timeout=QUEUE_TIMEOUT)
                    print("Audio queue processing completed")
                except asyncio.TimeoutError:
                    print("Timeout waiting for audio queue to be processed")

            # Double-check audio data still exists before transcription
            current_size = len(self.audio_data) if self.audio_data else 0
            print(f"[DEBUG] Audio data size before transcription: {current_size} bytes")

            if not self.audio_data or current_size == 0:
                print("Audio data was cleared before transcription")
                return "[Audio data cleared before transcription]"

            # Pass the client to transcribe_audio
            if TRANSCRIBE_GENERATED_AUDIO:
                print(f"[DEBUG] Calling transcribe_audio with {len(self.audio_data)} bytes")
                transcribed_text = await transcribe_audio(self.audio_data, self.client)
            else:
                # Transcription disabled - skip the second API call entirely. The
                # sentinel below still fires so the client can finalize the turn.
                print(f"[DEBUG] Transcription disabled, skipping API call for {len(self.audio_data)} bytes")
                transcribed_text = None

            # Always attempt to send transcription if we have audio data, even if transcription failed
            if self.audio_data and self.websocket.state not in (websockets.protocol.State.CLOSED, websockets.protocol.State.CLOSING):
                # Use transcribed text if available, otherwise provide a fallback message
                if not TRANSCRIBE_GENERATED_AUDIO:
                    # The session's own output transcription: what the model
                    # actually spoke, gathered free alongside the audio. Empty
                    # when the model produced no speech, which is itself worth
                    # reporting.
                    message_text = self.spoken_text.strip()
                    is_error = False
                elif transcribed_text:
                    cleaned_text = transcribed_text.replace("GEMINI: ", "")
                    print(f"Transcribed text: {cleaned_text[:50]}...")

                    # Check for duplicate transcription before sending
                    if self._is_duplicate_transcription(cleaned_text):
                        print(f"Skipping duplicate transcription: {cleaned_text[:30]}...")
                        return cleaned_text  # Return the text but don't send it

                    message_text = cleaned_text
                    is_error = cleaned_text.startswith("[") and cleaned_text.endswith("]")
                else:
                    # No transcription result - send a generic message
                    message_text = "[Speech detected but transcription unavailable]"
                    is_error = True
                    print("No transcription result, sending generic message")

                audio_base64 = base64.b64encode(self.audio_data).decode('utf-8')
                send_success = False

                # Reduced retry attempts for faster transcription sending
                for attempt in range(2):
                    if self.websocket.state not in (websockets.protocol.State.CLOSED, websockets.protocol.State.CLOSING):
                        send_success = await self.safe_send({
                            "text": message_text,
                            "is_transcription": True,
                            "is_error": is_error,
                            "audio_data": audio_base64,
                            "audio_format": "audio/pcm;rate=24000"
                        })
                        if send_success:
                            print(f"Transcription sent to client (attempt {attempt+1})")
                            break
                        else:
                            print(f"Failed to send transcription (attempt {attempt+1}), retrying...")
                            await asyncio.sleep(RETRY_DELAY)
                    else:
                        print("WebSocket closed, cannot send transcription")
                        break

                return message_text
            else:
                if not self.audio_data:
                    print("No audio data available for transcription")
                else:
                    print("WebSocket closed, cannot send transcription")
                return None

        except Exception as e:
            print(f"Error processing transcription: {e}")
            return f"[Transcription error: {str(e)[:50]}...]"
        finally:
            # Reset audio data and state after processing
            print(f"Resetting audio processor after transcription (was {len(self.audio_data) if self.audio_data else 0} bytes)")
            self.reset() 