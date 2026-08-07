"""Focused offline contracts for the modularized response/audio backend."""

import asyncio
import base64
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# The legacy implementation reads State through this module attribute.
import websockets.protocol  # noqa: E402,F401

import main_server_files.server_initialization  # noqa: E402,F401
from main_server_files.audio_processing import audio_processor as audio_module  # noqa: E402
from main_server_files.audio_processing.audio_processor import AudioProcessor  # noqa: E402
from main_server_files.response_processing.response_frame_processor import (  # noqa: E402
    process_response_frame,
)
from main_server_files.response_processing.response_handler import (  # noqa: E402
    GeminiResponseHandler,
)


class FakeWebSocket:
    def __init__(self):
        self.state = websockets.protocol.State.OPEN
        self.messages = []

    async def send(self, payload):
        self.messages.append(json.loads(payload))


class FakeConnectionMonitor:
    def __init__(self):
        self.messages = []
        self.activity_count = 0

    def is_websocket_open(self):
        return True

    async def safe_send(self, payload):
        self.messages.append(json.loads(payload))
        return True

    def record_activity(self):
        self.activity_count += 1


class AudioProcessorContracts(unittest.IsolatedAsyncioTestCase):
    async def test_direct_transport_keeps_payload_and_activity_contract(self):
        websocket = FakeWebSocket()
        activity = []
        processor = AudioProcessor(
            websocket,
            "connection-1",
            update_activity_callback=lambda: activity.append(True),
        )

        await processor.process_audio_data(b"pcm", False)

        self.assertEqual(activity, [True])
        self.assertEqual(websocket.messages, [{
            "audio": base64.b64encode(b"pcm").decode("utf-8"),
            "sequential": False,
            "session_id": 1,
        }])

    async def test_large_sequential_audio_keeps_chunk_order_and_session(self):
        processor = AudioProcessor(FakeWebSocket(), "connection-2")
        audio = b"a" * (audio_module.MAX_CHUNK_SIZE + 3)

        await processor.process_audio_data(audio, True)

        first = processor.audio_queue.get_nowait()
        second = processor.audio_queue.get_nowait()
        self.assertEqual(first, (audio[:audio_module.MAX_CHUNK_SIZE], 1))
        self.assertEqual(second, (audio[audio_module.MAX_CHUNK_SIZE:], 1))
        processor.audio_queue.task_done()
        processor.audio_queue.task_done()

    async def test_turn_finalization_uses_session_transcript_then_resets(self):
        websocket = FakeWebSocket()
        processor = AudioProcessor(websocket, "connection-3")
        processor.audio_data = b"audio"
        processor.spoken_text = "the spoken passage"

        with (
            patch.object(audio_module, "TRANSCRIBE_GENERATED_AUDIO", False),
            patch.object(audio_module, "TRANSCRIBE_WHEN_SESSION_SILENT", False),
        ):
            result = await processor.process_turn_complete()

        self.assertEqual(result, "the spoken passage")
        self.assertEqual(websocket.messages[0]["text"], "the spoken passage")
        self.assertTrue(websocket.messages[0]["is_transcription"])
        self.assertEqual(processor.audio_data, b"")
        self.assertEqual(processor.spoken_text, "")


class ResponseHandlerContracts(unittest.IsolatedAsyncioTestCase):
    def make_audio_processor(self):
        class FakeAudioProcessor:
            def __init__(self):
                self.audio_data = b""
                self.spoken_text = ""
                self.is_sequential = True
                self.calls = []
                self.reset_count = 0

            async def process_audio_data(self, *args, **kwargs):
                self.calls.append((args, kwargs))

            async def process_turn_complete(self):
                return "done"

            def reset(self):
                self.reset_count += 1
                self.audio_data = b""

        return FakeAudioProcessor()

    async def test_both_audio_paths_share_buffering_without_reordering_calls(self):
        monitor = FakeConnectionMonitor()
        audio_processor = self.make_audio_processor()
        handler = GeminiResponseHandler(monitor, audio_processor)

        await handler.process_audio_response(b"normal")
        await handler.process_audio_chunk(b"direct")

        self.assertEqual(audio_processor.audio_data, b"normaldirect")
        self.assertEqual(
            audio_processor.calls,
            [((b"normal", True), {}), ((b"direct",), {"sequential": False})],
        )
        self.assertEqual(monitor.activity_count, 1)
        self.assertIsNotNone(handler.last_audio_time)

    async def test_final_frame_collects_transcript_before_scheduling_completion(self):
        monitor = FakeConnectionMonitor()
        audio_processor = self.make_audio_processor()
        handler = GeminiResponseHandler(monitor, audio_processor)
        scheduled_transcripts = []
        handler.schedule_turn_completion = lambda: scheduled_transcripts.append(
            audio_processor.spoken_text
        )
        response = SimpleNamespace(server_content=SimpleNamespace(
            output_transcription=SimpleNamespace(text="tail"),
            turn_complete=True,
        ))
        logger = SimpleNamespace(
            debug=lambda *args: None,
            info=lambda *args: None,
            warning=lambda *args: None,
            error=lambda *args: None,
        )

        await process_response_frame(response, handler, "connection-4", logger)

        self.assertEqual(audio_processor.spoken_text, "tail")
        self.assertEqual(scheduled_transcripts, ["tail"])


if __name__ == "__main__":
    unittest.main()
