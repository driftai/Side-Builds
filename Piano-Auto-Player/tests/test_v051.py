import csv
import tempfile
import unittest
from pathlib import Path

from app.audio_ghost_filter import conservative_ghost_config, filter_ghost_notes
from app.audio_note_cleanup import basic_pitch_args, performance_from_note_events, preset_for


class V051LowerSensitivityTests(unittest.TestCase):
    def test_default_clean_is_stricter_but_keeps_fast_floor(self):
        preset = preset_for("rhythm_clean")
        self.assertEqual(preset.onset_threshold, 0.50)
        self.assertEqual(preset.minimum_note_length_ms, 55.0)
        self.assertEqual(preset.min_velocity, 28)
        self.assertEqual(preset.max_chord_notes, 5)
        self.assertFalse(preset.use_melodia)

    def test_v050_sensitivity_remains_available(self):
        preset = preset_for("rhythm_clean_sensitive")
        self.assertEqual(preset.onset_threshold, 0.44)
        self.assertEqual(preset.min_velocity, 22)
        self.assertEqual(preset.max_chord_notes, 6)
        self.assertFalse(preset.use_melodia)

    def test_weak_one_sided_run_blip_is_removed_but_two_sided_fast_note_survives(self):
        cfg = conservative_ghost_config()
        one_sided = [(0.0, 80.0, 60, 76), (66.0, 126.0, 62, 30)]
        kept, dropped = filter_ghost_notes(one_sided, cfg)
        self.assertEqual(dropped, 1)
        self.assertNotIn(one_sided[1], kept)
        two_sided = [(0.0, 80.0, 60, 76), (66.0, 126.0, 62, 30), (132.0, 205.0, 64, 73)]
        kept, dropped = filter_ghost_notes(two_sided, cfg)
        self.assertEqual(dropped, 0)
        self.assertIn(two_sided[1], kept)

    def test_weak_long_isolated_energy_no_longer_survives_just_for_duration(self):
        note = (400.0, 760.0, 83, 30)
        kept, dropped = filter_ghost_notes([note], conservative_ghost_config())
        self.assertEqual(kept, [])
        self.assertEqual(dropped, 1)

    def test_61_key_transcription_limits_basic_pitch_frequency_range(self):
        args = basic_pitch_args(preset_for("rhythm_clean"), "61")
        self.assertEqual(args[args.index("--minimum-frequency") + 1], "65.406")
        self.assertEqual(args[args.index("--maximum-frequency") + 1], "2093.005")
        args88 = basic_pitch_args(preset_for("rhythm_clean"), "88")
        self.assertEqual(args88[args88.index("--minimum-frequency") + 1], "27.5")
        self.assertEqual(args88[args88.index("--maximum-frequency") + 1], "4186.01")

    def test_61_key_cleanup_drops_out_of_range_notes_instead_of_octave_folding(self):
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "notes.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["start_time_s", "end_time_s", "pitch_midi", "velocity", "pitch_bend"])
                writer.writerow([0.000, 0.120, 24, 90, ""])
                writer.writerow([0.000, 0.120, 60, 90, ""])
                writer.writerow([0.150, 0.260, 100, 90, ""])
            performance, stats = performance_from_note_events(path, preset_for("rhythm_clean"), "61")
        pitches = [span["midi"] for event in performance for span in event.get("note_spans", [])]
        self.assertEqual(pitches, [60])
        self.assertEqual(stats["cleanup_layout_drops"], 2)
        self.assertEqual(stats["folded_notes"], 0)
        self.assertEqual(stats["transcription_layout"], "61")

    def test_ui_sends_selected_layout_and_exposes_previous_sensitivity(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        api = Path("web/api.js").read_text(encoding="utf-8")
        js = Path("web/youtube_piano.js").read_text(encoding="utf-8")
        server = Path("app/server.py").read_text(encoding="utf-8")
        self.assertIn('value="rhythm_clean_sensitive"', html)
        self.assertIn('piano_layout: pianoLayout', api)
        self.assertIn('document.getElementById("pianoLayout")', js)
        self.assertIn('layout?.value || "61"', js)
        self.assertIn('str(payload.get("piano_layout") or "61")', server)
        self.assertIn("Piano Auto Player v", html)
        self.assertIn("Piano Auto Player v", server)

    def test_source_line_cap(self):
        for name in [
            "app/audio_ghost_filter.py", "app/audio_note_cleanup.py", "app/audio_transcriber.py",
            "app/performance_lifecycle.py", "app/performance_notes.py", "app/playback.py",
            "app/server.py", "web/youtube_piano.js", "web/app.js",
        ]:
            lines = len(Path(name).read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(lines, 450, f"{name} exceeded 450 lines ({lines})")


if __name__ == "__main__":
    unittest.main()
