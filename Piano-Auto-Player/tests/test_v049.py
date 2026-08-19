import csv
import tempfile
import unittest
from pathlib import Path

from app.audio_ghost_filter import GhostGuardConfig, filter_ghost_notes
from app.audio_note_cleanup import performance_from_note_events, preset_for


class V049GhostNoteGuardTests(unittest.TestCase):
    def test_weak_isolated_short_note_is_removed(self):
        notes = [
            (0.0, 180.0, 60, 80),
            (500.0, 555.0, 83, 25),
            (1000.0, 1180.0, 64, 76),
        ]
        kept, dropped = filter_ghost_notes(notes, GhostGuardConfig())
        self.assertEqual(dropped, 1)
        self.assertNotIn(notes[1], kept)

    def test_weak_fast_run_note_is_preserved_by_local_support(self):
        notes = [
            (0.0, 70.0, 60, 72),
            (62.0, 118.0, 62, 25),
            (124.0, 190.0, 64, 70),
        ]
        kept, dropped = filter_ghost_notes(notes, GhostGuardConfig())
        self.assertEqual(dropped, 0)
        self.assertEqual(kept, notes)

    def test_weak_sustained_note_is_preserved(self):
        note = (400.0, 700.0, 48, 25)
        kept, dropped = filter_ghost_notes([note], GhostGuardConfig())
        self.assertEqual(kept, [note])
        self.assertEqual(dropped, 0)

    def test_rhythm_clean_reports_ghost_drops_but_keeps_fast_sequence(self):
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "notes.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["start_time_s", "end_time_s", "pitch_midi", "velocity", "pitch_bend"])
                writer.writerow([0.000, 0.080, 60, 80, ""])
                writer.writerow([0.060, 0.120, 62, 25, ""])
                writer.writerow([0.120, 0.190, 64, 78, ""])
                writer.writerow([0.500, 0.550, 91, 25, ""])
            performance, stats = performance_from_note_events(path, preset_for("rhythm_clean_sensitive"))
        self.assertEqual(stats["transcription_quality"], "rhythm_clean_sensitive")
        self.assertEqual(stats["cleanup_ghost_drops"], 1)
        pitches = [span["midi"] for event in performance for span in event.get("note_spans", [])]
        self.assertIn(62, pitches)
        self.assertNotIn(91, pitches)

    def test_old_rhythm_mode_remains_available_without_ghost_guard(self):
        self.assertEqual(preset_for("rhythm").key, "rhythm")
        self.assertEqual(preset_for(None).key, "rhythm_clean")

    def test_ui_runtime_and_line_cap(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        server = Path("app/server.py").read_text(encoding="utf-8")
        js = Path("web/youtube_piano.js").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v", html)
        self.assertIn("Piano Auto Player v", server)
        self.assertIn('value="rhythm_clean"', html)
        self.assertIn("ghost guard removed", js)
        for name in [
            "app/audio_ghost_filter.py", "app/audio_note_cleanup.py", "app/audio_transcriber.py",
            "app/performance_lifecycle.py", "app/performance_notes.py", "app/playback.py",
            "app/server.py", "web/youtube_piano.js", "web/app.js",
        ]:
            lines = len(Path(name).read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(lines, 450, f"{name} exceeded 450 lines ({lines})")


if __name__ == "__main__":
    unittest.main()
