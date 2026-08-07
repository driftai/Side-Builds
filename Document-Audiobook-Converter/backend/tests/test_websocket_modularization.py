#!/usr/bin/env python3
"""Offline regression checks for the modular websocket facades and routing."""

import inspect
import json
import pathlib
import sys
import unittest
from unittest import mock


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from main_server_files.websocket_server.websocket_protocol import (  # noqa: E402
    HISTORY,
    LEGACY_COMMAND,
    LEGACY_PING,
    MEDIA,
    REALTIME_INPUT,
    SETUP,
    SILENT_TIME_UPDATE,
    TYPED_PING,
    TYPED_UNKNOWN,
    UNKNOWN,
    build_history_context,
    classify_client_message,
    extract_setup_metadata,
    format_history_message,
)


class ProtocolTests(unittest.TestCase):
    def test_first_match_branch_precedence_is_stable(self):
        self.assertEqual(
            classify_client_message({"setup": {}, "type": "ping"}),
            SETUP,
        )
        self.assertEqual(
            classify_client_message({"type": "mystery", "realtime_input": {}}),
            TYPED_UNKNOWN,
        )
        self.assertEqual(
            classify_client_message({"realtime_input": {}, "command": "go"}),
            REALTIME_INPUT,
        )
        self.assertEqual(
            classify_client_message({"command": "go", "ping": True}),
            LEGACY_COMMAND,
        )
        self.assertEqual(
            classify_client_message({"ping": 1}),
            LEGACY_PING,
        )
        self.assertEqual(
            classify_client_message({
                "is_time_update": True,
                "is_silent_update": True,
            }),
            SILENT_TIME_UPDATE,
        )
        self.assertEqual(
            classify_client_message({"history": [], "audio": "bytes"}),
            HISTORY,
        )
        self.assertEqual(classify_client_message({"audio": "bytes"}), MEDIA)
        self.assertEqual(classify_client_message({}), UNKNOWN)

    def test_typed_ping_aliases_are_preserved(self):
        for message_type in (
            "application_ping", "ping", "keepalive", "heartbeat",
        ):
            with self.subTest(message_type=message_type):
                self.assertEqual(
                    classify_client_message({"type": message_type}),
                    TYPED_PING,
                )

    def test_setup_metadata_uses_legacy_shape_and_default(self):
        _, model, voice = extract_setup_metadata({"setup": {}})
        self.assertEqual(model, "gemini-2.0-flash-live-001")
        self.assertIsNone(voice)

        _, model, voice = extract_setup_metadata({
            "setup": {
                "model": "custom-model",
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": "Aoede"},
                    },
                },
            },
        })
        self.assertEqual(model, "custom-model")
        self.assertEqual(voice, "Aoede")

    def test_history_payload_and_context_are_unchanged(self):
        history = [
            {
                "role": "user",
                "content": "Hello",
                "timestamp": "2026-08-07T13:05:00",
            },
            {
                "role": "assistant",
                "content": "Hi",
                "timestamp": "invalid",
            },
        ]
        self.assertEqual(format_history_message(history[0]), {
            "text": "YOU: Hello",
            "timestamp": "08/07/2026 01:05 PM",
            "is_history": True,
        })
        self.assertEqual(build_history_context(history), [
            {"role": "user", "parts": [{"text": "Hello"}]},
            {"role": "model", "parts": [{"text": "Hi"}]},
        ])


class FakeMonitor:
    def __init__(self):
        self.sent = []
        self.activity_count = 0

    async def safe_send(self, payload):
        self.sent.append(json.loads(payload))

    def record_activity(self):
        self.activity_count += 1


class FakeSession:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class FakeWebsocket:
    def __init__(self, messages):
        self.messages = list(messages)

    async def recv(self):
        return json.dumps(self.messages.pop(0))


class FakeMessageStream:
    def __init__(self, messages):
        self.messages = iter(messages)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.messages)
        except StopIteration as error:
            raise StopAsyncIteration from error


class HandshakeTests(unittest.IsolatedAsyncioTestCase):
    async def test_startup_commands_keep_clear_then_history_then_config_order(self):
        from main_server_files.server_initialization import main_entry  # noqa: F401
        from main_server_files.websocket_server import session_handshake

        monitor = FakeMonitor()
        websocket = FakeWebsocket([
            {"command": "clear_history"},
            {"command": "get_history"},
            {"voice": "Aoede", "model": "model-x"},
        ])
        clear_history = mock.Mock()
        with (
            mock.patch.object(
                session_handshake,
                "clear_chat_history",
                clear_history,
            ),
            mock.patch.object(
                session_handshake,
                "load_chat_history",
                return_value=[],
            ),
        ):
            result = await session_handshake.receive_initial_configuration(
                websocket,
                monitor,
                41,
                object(),
            )

        self.assertTrue(result.proceed)
        self.assertEqual(result.data, {"voice": "Aoede", "model": "model-x"})
        clear_history.assert_called_once_with()
        self.assertEqual(
            [message["text"] for message in monitor.sent],
            ["Chat history cleared", "No chat history found"],
        )


class DispatchTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _dispatcher():
        # Import through the production entry path. This initializes the existing
        # package graph in the same order as backend/main.py, without opening a
        # socket or making an API request.
        from main_server_files.server_initialization import main_entry  # noqa: F401
        from main_server_files.websocket_server.message_dispatch import (
            dispatch_client_message,
        )
        return dispatch_client_message

    async def test_status_acknowledgment(self):
        monitor = FakeMonitor()
        should_continue = await self._dispatcher()(
            {"type": "connection_test"},
            FakeSession(),
            monitor,
            42,
            object(),
            session_registry={},
        )
        self.assertTrue(should_continue)
        self.assertEqual(monitor.sent[0]["type"], "status_acknowledgment")
        self.assertEqual(monitor.sent[0]["received_type"], "connection_test")

    async def test_explicit_disconnect_closes_current_session(self):
        monitor = FakeMonitor()
        session = FakeSession()
        should_continue = await self._dispatcher()(
            {"type": "disconnect"},
            session,
            monitor,
            43,
            object(),
            session_registry={},
        )
        self.assertFalse(should_continue)
        self.assertTrue(session.closed)

    async def test_setup_updates_registry_and_acknowledges(self):
        monitor = FakeMonitor()
        registry = {44: {"voice_name": "Old"}}
        should_continue = await self._dispatcher()(
            {
                "setup": {
                    "model": "model-x",
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {"voiceName": "Kore"},
                        },
                    },
                },
            },
            FakeSession(),
            monitor,
            44,
            object(),
            session_registry=registry,
        )
        self.assertTrue(should_continue)
        self.assertEqual(registry[44]["model"], "model-x")
        self.assertEqual(registry[44]["voice_name"], "Kore")
        self.assertEqual(monitor.sent[0]["type"], "setup_acknowledgment")

    async def test_facade_keeps_json_error_then_disconnect_sequence(self):
        self._dispatcher()
        from main_server_files.websocket_server.message_processor import (
            send_to_gemini,
        )

        monitor = FakeMonitor()
        session = FakeSession()
        websocket = FakeMessageStream([
            "not-json",
            json.dumps({"type": "disconnect"}),
        ])
        await send_to_gemini(
            session,
            websocket,
            monitor,
            45,
            object(),
        )

        self.assertEqual(monitor.activity_count, 2)
        self.assertEqual(monitor.sent[0]["type"], "json_error")
        self.assertTrue(session.closed)


class FacadeTests(unittest.TestCase):
    def test_websocket_server_defaults_to_loopback(self):
        from main_server_files.server_initialization.server_config import (
            DEFAULT_BIND_HOST,
        )
        from main_server_files.websocket_server.websocket_server_handler import (
            initialize_websocket_server,
        )

        host = inspect.signature(initialize_websocket_server).parameters['host']
        self.assertEqual(DEFAULT_BIND_HOST, '127.0.0.1')
        self.assertEqual(host.default, DEFAULT_BIND_HOST)

    def test_public_async_signatures_are_compatible(self):
        from main_server_files.server_initialization.main_entry import (
            gemini_session_handler,
        )
        from main_server_files.websocket_server.message_processor import (
            send_to_gemini,
        )

        self.assertTrue(inspect.iscoroutinefunction(gemini_session_handler))
        self.assertTrue(inspect.iscoroutinefunction(send_to_gemini))
        self.assertEqual(
            str(inspect.signature(gemini_session_handler)),
            "(websocket)",
        )
        self.assertEqual(
            str(inspect.signature(send_to_gemini)),
            "(session, websocket, connection_monitor, connection_id, "
            "audio_processor, client=None)",
        )


if __name__ == "__main__":
    unittest.main()
