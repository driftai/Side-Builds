import struct
import unittest
from pathlib import Path

from app.midi_performance import midi_to_performance
from app.piano_layout import stroke_for_midi, target_midi_notes
from app.playback import PlaybackController, PlaybackOptions
from app.preview_timeline import build_performance_preview
from tests.test_v034 import _two_note_chord_midi, _vlq


def _fold_collision_midi() -> bytes:
    track = bytearray()
    track += b"\x00\x90\x15\x50"  # A0
    track += b"\x00\x90\x21\x50"  # A1, same pitch class and same folded 61-key token
    track += _vlq(240) + b"\x80\x15\x00"
    track += b"\x00\x80\x21\x00\x00\xff\x2f\x00"
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, 480) + b"MTrk" + struct.pack(">I", len(track)) + bytes(track)


class V037PianoLayoutTests(unittest.TestCase):
    def test_full_88_layout_matches_ctrl_extension_screenshot(self):
        expected = {
            21: ("1", True), 22: ("2", True), 35: ("t", True),
            36: ("1", False), 37: ("!", False), 96: ("m", False),
            97: ("y", True), 98: ("u", True), 108: ("j", True),
        }
        for midi, pair in expected.items():
            stroke = stroke_for_midi(midi, "88")
            self.assertIsNotNone(stroke)
            self.assertEqual((stroke.char, stroke.ctrl), pair)
            self.assertEqual(stroke.midi, midi)

    def test_switching_layout_changes_edge_pitch_without_reimport(self):
        source = [21, 60, 108]
        self.assertEqual(target_midi_notes(source, "88"), [21, 60, 108])
        self.assertEqual(target_midi_notes(source, "61"), [45, 60, 96])

    def test_midi_import_preserves_original_notes_for_later_translation(self):
        performance, _stats = midi_to_performance(_two_note_chord_midi())
        self.assertEqual(performance[0]["midi_notes"], [60, 64])
        cleaned = PlaybackController._clean_performance(performance)
        self.assertEqual(cleaned[0]["midi_notes"], [60, 64])

    def test_88_mode_recovers_notes_that_collide_when_61_key_folded(self):
        performance, _stats = midi_to_performance(_fold_collision_midi())
        self.assertEqual(len(performance[0]["key"]), 1)
        self.assertEqual(performance[0]["midi_notes"], [21, 33])
        strokes = [stroke_for_midi(note, "88") for note in performance[0]["midi_notes"]]
        self.assertEqual([(row.char, row.ctrl) for row in strokes], [("1", True), ("e", True)])

    def test_internal_preview_hears_selected_target_layout(self):
        event = [{"key": "am", "midi_notes": [21, 108], "at_ms": 0, "duration_ms": 500}]
        full = build_performance_preview(event, PlaybackOptions(timing_profile="midi", piano_layout="88"))
        standard = build_performance_preview(event, PlaybackOptions(timing_profile="midi", piano_layout="61"))
        self.assertEqual(full["events"][0]["midi_notes"], [21, 108])
        self.assertEqual(standard["events"][0]["midi_notes"], [45, 96])

    def test_ui_exposes_both_piano_lengths(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        js = Path("web/app.js").read_text(encoding="utf-8")
        preview = Path("web/internal_preview.js").read_text(encoding="utf-8")
        self.assertIn('id="pianoLayout"', html)
        self.assertIn('value="61"', html)
        self.assertIn('value="88"', html)
        self.assertIn('piano_layout: els.pianoLayout.value', js)
        self.assertIn('row.midi_notes', preview)


if __name__ == "__main__":
    unittest.main()
