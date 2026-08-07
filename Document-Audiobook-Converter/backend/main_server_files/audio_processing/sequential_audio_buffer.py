"""Sequential-session queue consumption for ``AudioProcessor``."""

import asyncio

from .audio_transport import websocket_is_open


async def process_audio_queue(processor, retry_delay):
    """Consume audio chunks in their existing session-grouped order."""
    current_session = None
    session_chunks = []

    try:
        while True:
            if not websocket_is_open(processor.websocket):
                print(
                    f"Connection {processor.connection_id} closed, stopping "
                    "audio queue processing"
                )
                break

            try:
                queue_item = await processor.audio_queue.get()
                if isinstance(queue_item, tuple):
                    audio_data, session_id = queue_item
                else:
                    # Backward compatibility for the original bare-byte format.
                    audio_data = queue_item
                    session_id = "legacy"

                if session_id != current_session:
                    if current_session is not None and session_chunks:
                        await processor._send_session_audio(
                            session_chunks, current_session
                        )
                        session_chunks = []

                    current_session = session_id
                    print(f"Starting new audio session: {session_id}")

                session_chunks.append(audio_data)
                processor.audio_queue.task_done()
            except Exception as error:
                print(f"Error processing audio queue: {error}")
                await asyncio.sleep(retry_delay)
    except asyncio.CancelledError:
        print("Audio queue processor cancelled")
        if session_chunks:
            try:
                await processor._send_session_audio(
                    session_chunks, current_session or "cancelled"
                )
            except Exception as error:
                print(f"Error sending remaining audio on cancellation: {error}")
    except Exception as error:
        print(f"Error in audio queue processor: {error}")
