import csv
import tempfile
import unittest
from pathlib import Path

from app.audio_note_cleanup import performance_from_note_events, preset_for
from app.audio_sustain_repair import SustainRepairConfig, repair_sustain_fragments


class V052SustainContinuityTests(unittest.TestCase):
    def test_long_same_pitch_fragments_across_tiny_gap_are_joined(self):
        notes = [
            (0.0, 410.0, 60, 57),
            (432.0, 810.0, 60, 55),
        ]
        repaired, joins = repair_sustain_fragments(notes)
        self.assertEqual(joins, 1)
        self.assertEqual(repaired, [(0.0, 810.0, 60, 57)])

    def test_short_repeated_notes_are_not_mistaken_for_sustain(self):
        notes = [
            (0.0, 82.0, 60, 61),
            (104.0, 188.0, 60, 62),
        ]
        repaired, joins = repair_sustain_fragments(notes)
        self.assertEqual(joins, 0)
        self.assertEqual(repaired, notes)

    def test_clear_stronger_reattack_survives_after_long_note(self):
        notes = [
            (0.0, 360.0, 64, 47),
            (388.0, 620.0, 64, 65),
        ]
        repaired, joins = repair_sustain_fragments(notes, SustainRepairConfig())
        self.assertEqual(joins, 0)
        self.assertEqual(repaired, notes)

    def test_one_frame_dropout_can_join_even_with_velocity_change(self):
        notes = [
            (0.0, 340.0, 67, 44),
            (351.0, 610.0, 67, 62),
        ]
        repaired, joins = repair_sustain_fragments(notes)
        self.assertEqual(joins, 1)
        self.assertEqual(repaired[0][1], 610.0)

    def test_cleanup_emits_one_continuous_span_and_reports_join(self):
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "notes.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["start_time_s", "end_time_s", "pitch_midi", "velocity", "pitch_bend"])
                writer.writerow([0.000, 0.410, 60, 57, ""])
                writer.writerow([0.432, 0.810, 60, 55, ""])
                writer.writerow([0.900, 1.020, 64, 75, ""])
            performance, stats = performance_from_note_events(path, preset_for("rhythm_clean"), "61")
        spans = [span for event in performance for span in event.get("note_spans", []) if span["midi"] == 60]
        self.assertEqual(len(spans), 1)
        self.assertAlmostEqual(spans[0]["duration_ms"], 810.0, places=2)
        self.assertEqual(stats["cleanup_sustain_joins"], 1)

    def test_rhythm_preserve_remains_unstitched_for_maximum_raw_detail(self):
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "notes.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["start_time_s", "end_time_s", "pitch_midi", "velocity", "pitch_bend"])
                writer.writerow([0.000, 0.410, 60, 57, ""])
                writer.writerow([0.432, 0.810, 60, 55, ""])
            performance, stats = performance_from_note_events(path, preset_for("rhythm"), "61")
        spans = [span for event in performance for span in event.get("note_spans", []) if span["midi"] == 60]
        self.assertEqual(len(spans), 2)
        self.assertEqual(stats["cleanup_sustain_joins"], 0)

    def test_v052_ui_and_line_cap(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        js = Path("web/youtube_piano.js").read_text(encoding="utf-8")
        server = Path("app/server.py").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v0.5.", html)
        self.assertIn("sustain repair joined", js)
        self.assertIn("Piano Auto Player v0.5.", server)
        for name in [
            "app/audio_sustain_repair.py", "app/audio_note_cleanup.py", "app/audio_ghost_filter.py",
            "app/audio_transcriber.py", "app/performance_lifecycle.py", "app/server.py",
            "web/youtube_piano.js", "web/app.js",
        ]:
            lines = len(Path(name).read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(lines, 450, f"{name} exceeded 450 lines ({lines})")


if __name__ == "__main__":
    unittest.main()
