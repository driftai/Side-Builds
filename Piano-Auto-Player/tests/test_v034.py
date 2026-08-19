import struct
import unittest
from pathlib import Path
from unittest.mock import patch

from app.midi_performance import fold_midi_note, midi_to_performance
from app.providers.musicboxmaniacs import MusicBoxManiacsProvider
from app.providers.onlinesequencer import OnlineSequencerProvider
from app.providers.onlinesequencer_proto import proto_to_performance
from app.providers.registry import ProviderRegistry


def _vlq(value: int) -> bytes:
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append(0x80 | (value & 0x7F))
        value >>= 7
    return bytes(reversed(out))


def _two_note_chord_midi() -> bytes:
    track = bytearray()
    track += b"\x00\xff\x51\x03\x07\xa1\x20"  # 120 BPM
    track += b"\x00\x90\x3c\x50"                 # C4 on
    track += b"\x00\x90\x40\x50"                 # E4 on, same tick
    track += _vlq(480) + b"\x80\x3c\x00"           # C4 off after quarter note
    track += b"\x00\x80\x40\x00"                 # E4 off, same tick
    track += b"\x00\xff\x2f\x00"
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, 480) + b"MTrk" + struct.pack(">I", len(track)) + bytes(track)


def _pb_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _pb_len(field: int, payload: bytes) -> bytes:
    return _pb_varint((field << 3) | 2) + _pb_varint(len(payload)) + payload


def _pb_int(field: int, value: int) -> bytes:
    return _pb_varint(field << 3) + _pb_varint(value)


def _pb_float(field: int, value: float) -> bytes:
    return _pb_varint((field << 3) | 5) + struct.pack("<f", value)


def _online_sequence_proto() -> bytes:
    settings = _pb_int(1, 120)
    def note(note_type: int) -> bytes:
        return _pb_int(1, note_type) + _pb_float(2, 0.0) + _pb_float(3, 4.0) + _pb_int(4, 0)
    return _pb_len(1, settings) + _pb_len(2, note(60)) + _pb_len(2, note(64))


class V034ProviderAndTimingTests(unittest.TestCase):
    def test_registry_restores_mbm_and_adds_online_sequencer(self):
        ids = [row["id"] for row in ProviderRegistry().info()]
        self.assertGreaterEqual(len(ids), 11)
        self.assertIn("musicboxmaniacs", ids)
        self.assertIn("onlinesequencer", ids)
        self.assertIn("toonkeys", ids)

    def test_midi_parser_groups_simultaneous_note_ons_as_real_chord(self):
        performance, stats = midi_to_performance(_two_note_chord_midi())
        self.assertEqual(len(performance), 1)
        self.assertEqual(len(performance[0]["key"]), 2)
        self.assertEqual(performance[0]["at_ms"], 0)
        self.assertEqual(performance[0]["duration_ms"], 500)
        self.assertEqual(stats["chord_count"], 1)

    def test_out_of_range_midi_notes_octave_fold_into_c2_c7(self):
        self.assertEqual(fold_midi_note(24), (36, True))
        self.assertEqual(fold_midi_note(108), (96, True))
        self.assertEqual(fold_midi_note(60), (60, False))

    def test_online_sequencer_search_finds_exact_avid_sequence(self):
        page = '<html><body><a href="/4619865">Avid - 86 / Eighty-Six (Episode 22 version) ED [Piano] / Hiroyuki Sawano</a></body></html>'
        with patch("app.providers.onlinesequencer.get_html", return_value=(page, "https://onlinesequencer.net/sequences?search=Avid")) as mocked:
            rows = OnlineSequencerProvider().search("Avid 86 Eighty-Six Hiroyuki Sawano")
        self.assertEqual(rows[0]["url"], "https://onlinesequencer.net/4619865")
        self.assertEqual(rows[0]["fidelity"], "midi")
        self.assertIn("search=", mocked.call_args.args[0])


    def test_online_sequencer_uses_current_proto_api_as_timed_performance(self):
        proto = _online_sequence_proto()
        performance, stats = proto_to_performance(proto)
        self.assertEqual(len(performance), 1)
        self.assertEqual(len(performance[0]["key"]), 2)
        self.assertEqual(performance[0]["duration_ms"], 500)
        self.assertEqual(stats["source_bpm"], 120.0)

        page = "<title>Avid - 86 / Eighty-Six (Episode 22 version) ED [Piano] / Hiroyuki Sawano - Online Sequencer</title>"
        with patch("app.providers.onlinesequencer.get_html", return_value=(page, "https://onlinesequencer.net/4619865")), \
             patch("app.providers.onlinesequencer.get_bytes", return_value=(proto, "https://onlinesequencer.net/app/api/get_proto.php?id=4619865")) as mocked:
            song = OnlineSequencerProvider().fetch("https://onlinesequencer.net/4619865")
        self.assertEqual(song["timing_profile"], "midi")
        self.assertEqual(song["performance"], performance)
        self.assertIn("get_proto.php?id=4619865", mocked.call_args.args[0])

    def test_music_box_maniacs_discovers_current_midi_export_link(self):
        page = '<a href="/exports/scale_132433.mid">download</a><a href="/exports/scale.mp3">download</a>'
        url = MusicBoxManiacsProvider._midi_url(page, "https://musicboxmaniacs.com/explore/melody/scale_132433/")
        self.assertEqual(url, "https://musicboxmaniacs.com/exports/scale_132433.mid")

    def test_non_timed_import_always_gets_fresh_timing_baseline(self):
        class FakeProvider:
            id = "fake"
            def accepts(self, _url): return True
            def fetch(self, _url): return {"title": "Fresh song", "sheet": "abc"}

        registry = ProviderRegistry()
        fake = FakeProvider()
        registry.providers.insert(0, fake)
        registry.by_id["fake"] = fake
        song = registry.fetch("https://example.invalid/song", "fake")
        self.assertEqual(song["recommended_interval_ms"], 115.0)
        app_js = Path("web/app.js").read_text(encoding="utf-8")
        self.assertIn('activePerformance.length ? 0 : 115', app_js)


if __name__ == "__main__":
    unittest.main()
