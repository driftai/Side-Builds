"""WebSocket transport helpers for ``AudioProcessor``."""

import asyncio
import base64
import json

import websockets


def websocket_is_open(websocket):
    """Match the processor's established websocket state check."""
    return websocket.state not in (
        websockets.protocol.State.CLOSED,
        websockets.protocol.State.CLOSING,
    )


async def safe_send(processor, message, stream_timeout):
    """Send a JSON message with the processor's timeout and activity callback."""
    try:
        if websocket_is_open(processor.websocket):
            await asyncio.wait_for(
                processor.websocket.send(json.dumps(message)),
                timeout=stream_timeout,
            )
            if processor.update_activity_callback:
                processor.update_activity_callback()
            return True
        return False
    except asyncio.TimeoutError:
        print(f"Timeout sending message to connection {processor.connection_id}")
        return False
    except Exception as error:
        print(
            f"Error sending message to connection {processor.connection_id}: "
            f"{error}"
        )
        return False


async def send_session_audio(
    processor,
    chunks,
    session_id,
    retry_delay,
    sequential_delay,
):
    """Send all queued chunks for one sequential session as one block."""
    if not chunks:
        return

    try:
        processor.is_playing_audio = True
        print(f"Sending audio session {session_id} with {len(chunks)} chunks")
        combined_audio = b''.join(chunks)
        base64_audio = base64.b64encode(combined_audio).decode('utf-8')

        for attempt in range(3):
            if websocket_is_open(processor.websocket):
                send_success = await processor.safe_send({
                    "audio": base64_audio,
                    "sequential": True,
                    "session_id": session_id,
                    "complete_session": True,
                })
                if send_success:
                    print(
                        f"Session {session_id} audio sent to client "
                        f"(attempt {attempt + 1})"
                    )
                    break
                print(
                    f"Failed to send session {session_id} audio "
                    f"(attempt {attempt + 1}), retrying..."
                )
                await asyncio.sleep(retry_delay * (attempt + 1))
            else:
                print(
                    f"WebSocket closed for connection {processor.connection_id}, "
                    f"cannot send session {session_id}"
                )
                break

        await asyncio.sleep(sequential_delay)
    except Exception as error:
        print(f"Error sending session {session_id} audio: {error}")
    finally:
        processor.is_playing_audio = False


async def process_audio_data(
    processor,
    audio_data,
    is_sequential,
    max_chunk_size,
    retry_delay,
):
    """Route one audio block to sequential buffering or direct transport."""
    async with processor.audio_playback_lock:
        processor.audio_session_id += 1
        current_session = processor.audio_session_id
        print(
            f"Starting audio session {current_session} with "
            f"{len(audio_data)} bytes"
        )

        if is_sequential is None:
            is_sequential = processor.is_sequential

        if len(audio_data) > max_chunk_size:
            print(
                f"Audio data ({len(audio_data)} bytes) exceeds max chunk size "
                f"({max_chunk_size}), chunking..."
            )
            await processor._process_chunked_audio(
                audio_data, is_sequential, current_session
            )
            return

        if is_sequential:
            await processor.audio_queue.put((audio_data, current_session))
            print(
                "Added audio chunk to sequential queue, size: "
                f"{processor.audio_queue.qsize()}, session: {current_session}"
            )
            return

        base64_audio = base64.b64encode(audio_data).decode('utf-8')
        for attempt in range(3):
            if websocket_is_open(processor.websocket):
                send_success = await processor.safe_send({
                    "audio": base64_audio,
                    "sequential": False,
                    "session_id": current_session,
                })
                if send_success:
                    print(
                        "Direct audio sent to client "
                        f"(attempt {attempt + 1}), session: {current_session}"
                    )
                    break
                print(
                    "Failed to send direct audio "
                    f"(attempt {attempt + 1}), retrying..."
                )
                await asyncio.sleep(retry_delay * (attempt + 1))
            else:
                print(
                    f"WebSocket closed for connection {processor.connection_id}, "
                    "cannot send audio"
                )
                break


async def process_chunked_audio(
    processor,
    audio_data,
    is_sequential,
    session_id,
    max_chunk_size,
    retry_delay,
):
    """Split a large block while preserving chunk order and retry cadence."""
    total_chunks = (len(audio_data) + max_chunk_size - 1) // max_chunk_size
    print(
        f"Processing {len(audio_data)} bytes in {total_chunks} chunks, "
        f"session: {session_id}"
    )

    for index in range(total_chunks):
        start_index = index * max_chunk_size
        end_index = min(start_index + max_chunk_size, len(audio_data))
        chunk = audio_data[start_index:end_index]
        try:
            if is_sequential:
                await processor.audio_queue.put((chunk, session_id))
                print(
                    f"Added chunk {index + 1}/{total_chunks} to sequential "
                    f"queue, session: {session_id}"
                )
            else:
                base64_chunk = base64.b64encode(chunk).decode('utf-8')
                send_success = False
                for attempt in range(2):
                    if websocket_is_open(processor.websocket):
                        send_success = await processor.safe_send({
                            "audio": base64_chunk,
                            "sequential": False,
                            "chunk_index": index,
                            "total_chunks": total_chunks,
                            "session_id": session_id,
                        })
                        if send_success:
                            print(
                                f"Chunk {index + 1}/{total_chunks} sent "
                                f"(attempt {attempt + 1}), session: {session_id}"
                            )
                            break
                        print(
                            f"Failed to send chunk {index + 1}/{total_chunks} "
                            f"(attempt {attempt + 1}), retrying..."
                        )
                        await asyncio.sleep(retry_delay)
                    else:
                        print(
                            "WebSocket closed during chunking for connection "
                            f"{processor.connection_id}"
                        )
                        return

                if not send_success:
                    print(
                        f"Failed to send chunk {index + 1}/{total_chunks} "
                        "after all retries"
                    )
                    break

            await asyncio.sleep(0.01)
        except Exception as error:
            print(
                f"Error processing chunk {index + 1}/{total_chunks}: {error}"
            )
            break
