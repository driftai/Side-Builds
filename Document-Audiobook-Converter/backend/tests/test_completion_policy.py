"""Regression coverage for authoritative Gemini turn completion."""

import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import main_server_files.server_initialization  # noqa: E402,F401
from main_server_files.response_processing.response_frame_processor import (  # noqa: E402
    process_response_frame,
)
from main_server_files.response_processing.response_handler import (  # noqa: E402
    GeminiResponseHandler,
)


class FakeConnectionMonitor:
    def is_websocket_open(self):
        return True

    async def safe_send(self, _payload):
        return True

    def record_activity(self):
        pass


class FakeAudioProcessor:
    def __init__(self):
        self.audio_data = b""
        self.spoken_text = ""
        self.is_sequential = True
        self.completion_calls = 0

    async def process_audio_data(self, _audio, _sequential=None, **_kwargs):
        pass

    async def process_turn_complete(self):
        self.completion_calls += 1
        self.audio_data = b""
        self.spoken_text = ""
        return None

    def reset(self):
        self.audio_data = b""


class ImmutableUnknownContent:
    """A response shape that cannot accept synthetic completion fields."""

    __slots__ = (
        "server_content", "output_transcription", "turn_complete",
        "model_turn", "audio_chunks", "inline_data", "final", "finished",
        "complete",
    )

    def __init__(self):
        object.__setattr__(self, "server_content", self)
        object.__setattr__(self, "output_transcription", None)
        object.__setattr__(self, "turn_complete", False)
        object.__setattr__(self, "model_turn", None)
        object.__setattr__(self, "audio_chunks", None)
        object.__setattr__(self, "inline_data", None)
        object.__setattr__(self, "final", False)
        object.__setattr__(self, "finished", False)
        object.__setattr__(self, "complete", False)

    def __setattr__(self, _name, _value):
        raise AttributeError("immutable SDK response")


class CompletionPolicyTests(unittest.IsolatedAsyncioTestCase):
    def make_handler(self):
        processor = FakeAudioProcessor()
        handler = GeminiResponseHandler(FakeConnectionMonitor(), processor)
        return handler, processor

    async def asyncTearDown(self):
        handler = getattr(self, "handler", None)
        if handler is not None:
            handler.cancel_pending_tasks()
        await asyncio.sleep(0)

    async def test_old_large_chunk_case_does_not_complete_after_point_18_seconds(self):
        self.handler, processor = self.make_handler()

        await self.handler.process_audio_response(b"x" * 405_120)
        await asyncio.sleep(0.22)

        self.assertEqual(processor.completion_calls, 0)
        self.assertEqual(len(processor.audio_data), 405_120)

    async def test_tiny_audio_is_not_force_completed_after_point_10_seconds(self):
        self.handler, processor = self.make_handler()

        await self.handler.process_audio_response(b"x" * 6_000)
        await asyncio.sleep(0.14)

        self.assertEqual(processor.completion_calls, 0)

    async def test_each_audio_chunk_restarts_the_single_idle_watchdog(self):
        self.handler, processor = self.make_handler()
        self.handler.FORCE_COMPLETE_SILENCE_SECONDS = 0.06

        await self.handler.process_audio_response(b"a" * 6_000)
        await asyncio.sleep(0.04)
        await self.handler.process_audio_response(b"b" * 6_000)
        await asyncio.sleep(0.04)
        self.assertEqual(processor.completion_calls, 0)

        for _ in range(20):
            if processor.completion_calls:
                break
            await asyncio.sleep(0.01)
        task = self.handler._idle_completion_task
        self.assertEqual(
            processor.completion_calls,
            1,
            f"watchdog={task!r}; done={task.done() if task else None}; "
            f"error={task.exception() if task and task.done() else None}; "
            f"last_audio_time={self.handler.last_audio_time}",
        )

    async def test_immutable_unknown_frame_waits_instead_of_completing(self):
        self.handler, processor = self.make_handler()
        await self.handler.process_audio_response(b"x" * 6_000)
        response = SimpleNamespace(server_content=ImmutableUnknownContent())

        await process_response_frame(
            response,
            self.handler,
            "completion-test",
            logging.getLogger("completion-test"),
        )

        self.assertEqual(processor.completion_calls, 0)

    async def test_explicit_turn_complete_wins_and_retires_the_watchdog(self):
        self.handler, processor = self.make_handler()
        self.handler.FORCE_COMPLETE_SILENCE_SECONDS = 0.05
        self.handler.TRANSCRIPT_SETTLE_SECONDS = 0.01
        await self.handler.process_audio_response(b"x" * 6_000)
        response = SimpleNamespace(server_content=SimpleNamespace(
            output_transcription=SimpleNamespace(text="spoken"),
            turn_complete=True,
        ))

        await process_response_frame(
            response,
            self.handler,
            "completion-test",
            logging.getLogger("completion-test"),
        )
        await asyncio.sleep(0.03)
        self.assertEqual(processor.completion_calls, 1)

        await asyncio.sleep(0.05)
        self.assertEqual(processor.completion_calls, 1)


if __name__ == "__main__":
    unittest.main()
