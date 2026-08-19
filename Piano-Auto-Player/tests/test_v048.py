import csv
import tempfile
import unittest
from pathlib import Path

from app.audio_note_cleanup import performance_from_note_events, preset_for
from app.library import SongLibrary
from app.performance_lifecycle import LifecycleAction, LifecycleKeyState, build_lifecycle_actions
from app.performance_notes import clean_performance
from app.piano_layout import PianoStroke
from app.playback import PlaybackOptions
from app.preview_timeline import build_performance_preview


class FakeKeyboard:
    def __init__(self):
        self.calls = []

    def press_strokes(self, strokes, *args):
        self.calls.append(("down", [(s.char, s.ctrl, s.midi) for s in strokes]))

    def release_strokes(self, strokes):
        self.calls.append(("up", [(s.char, s.ctrl, s.midi) for s in strokes]))


class V048NoteLifecycleTests(unittest.TestCase):
    def test_basic_pitch_cleanup_preserves_per_note_start_and_release(self):
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "notes.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["start_time_s", "end_time_s", "pitch_midi", "velocity", "pitch_bend"])
                writer.writerow([0.100, 0.900, 60, 96, ""])
                writer.writerow([0.110, 0.320, 64, 88, ""])
                writer.writerow([0.500, 0.620, 67, 92, ""])
            performance, _stats = performance_from_note_events(path, preset_for("rhythm"))
        self.assertEqual(len(performance), 2)
        first = performance[0]
        self.assertEqual(first["midi_notes"], [60, 64])
        spans = {span["midi"]: span for span in first["note_spans"]}
        self.assertAlmostEqual(spans[60]["duration_ms"], 800.0, places=2)
        self.assertAlmostEqual(spans[64]["offset_ms"], 10.0, places=2)
        self.assertAlmostEqual(spans[64]["duration_ms"], 210.0, places=2)

    def test_preview_keeps_sustain_across_later_onsets_when_spans_exist(self):
        events = [
            {"key": "a", "at_ms": 0, "duration_ms": 500, "midi_notes": [60],
             "note_spans": [{"midi": 60, "offset_ms": 0, "duration_ms": 500, "velocity": 90}]},
            {"key": "s", "at_ms": 80, "duration_ms": 90, "midi_notes": [62],
             "note_spans": [{"midi": 62, "offset_ms": 0, "duration_ms": 90, "velocity": 90}]},
        ]
        preview = build_performance_preview(events, PlaybackOptions(timing_profile="youtube_basic_pitch", piano_layout="88"))
        self.assertEqual(preview["events"][0]["note_spans"][0]["duration_ms"], 500.0)
        self.assertEqual(preview["events"][1]["at_ms"], 80.0)
        self.assertGreater(preview["events"][0]["duration_ms"], preview["events"][1]["at_ms"])

    def test_lifecycle_actions_have_independent_note_off_times(self):
        events = [{
            "key": "as", "at_ms": 100, "duration_ms": 600, "midi_notes": [60, 64],
            "note_spans": [
                {"midi": 60, "offset_ms": 0, "duration_ms": 600, "velocity": 90},
                {"midi": 64, "offset_ms": 12, "duration_ms": 180, "velocity": 80},
            ],
        }]
        actions = build_lifecycle_actions(events, "88")
        self.assertEqual([(a.kind, a.at_ms, a.stroke.midi) for a in actions], [
            ("down", 100.0, 60), ("down", 112.0, 64), ("up", 292.0, 64), ("up", 700.0, 60),
        ])

    def test_physical_key_collision_releases_old_owner_before_retrigger(self):
        keyboard = FakeKeyboard()
        state = LifecycleKeyState(keyboard, PlaybackOptions())
        black = PianoStroke("!", False, 37)
        white = PianoStroke("1", False, 36)
        state.apply_batch([LifecycleAction(0, "down", 1, "old", black, "1", 80, "!")])
        state.apply_batch([LifecycleAction(50, "down", 2, "new", white, "1", 90, "1")])
        state.apply_batch([LifecycleAction(100, "up", 1, "old", black, "1", 80, "!")])
        state.apply_batch([LifecycleAction(120, "up", 2, "new", white, "1", 90, "1")])
        self.assertEqual(keyboard.calls[0][0], "down")
        self.assertEqual(keyboard.calls[1][0], "up")
        self.assertEqual(keyboard.calls[2][0], "down")
        self.assertEqual(keyboard.calls[3][0], "up")
        self.assertEqual(len(keyboard.calls), 4)  # stale old note-off was ignored

    def test_cleaner_and_library_preserve_lifecycle_metadata(self):
        event = {
            "key": "aS", "at_ms": 10, "duration_ms": 100, "midi_notes": [60, 63],
            "note_spans": [
                {"midi": 60, "offset_ms": 0, "duration_ms": 400, "velocity": 95},
                {"midi": 63, "offset_ms": 8, "duration_ms": 120, "velocity": 82},
            ],
        }
        cleaned = clean_performance([event])[0]
        self.assertEqual(cleaned["key"], "aS")
        self.assertEqual(cleaned["midi_notes"], [60, 63])
        self.assertEqual(len(cleaned["note_spans"]), 2)
        with tempfile.TemporaryDirectory() as temp_name:
            library = SongLibrary(Path(temp_name) / "songs.json")
            saved = library.save({"title": "Lifecycle", "performance": [event], "timing_profile": "youtube_basic_pitch"})
        self.assertEqual(saved["performance"][0]["key"], "aS")
        self.assertEqual(saved["performance"][0]["midi_notes"], [60, 63])
        self.assertEqual(len(saved["performance"][0]["note_spans"]), 2)

    def test_ui_and_runtime_are_v048_and_internal_preview_reads_spans(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        server = Path("app/server.py").read_text(encoding="utf-8")
        preview = Path("web/internal_preview.js").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v", html)
        self.assertIn("Piano Auto Player v", server)
        self.assertIn("row.note_spans", preview)
        self.assertIn("_soundSpans", preview)

    def test_source_line_cap(self):
        for name in [
            "app/audio_note_cleanup.py", "app/audio_transcriber.py", "app/performance_lifecycle.py",
            "app/performance_notes.py", "app/playback.py", "app/preview_timeline.py", "app/server.py",
            "app/keyboard_win.py", "app/virtual_target.py", "web/internal_preview.js", "web/app.js",
        ]:
            lines = len(Path(name).read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(lines, 450, f"{name} exceeded 450 lines ({lines})")


if __name__ == "__main__":
    unittest.main()
