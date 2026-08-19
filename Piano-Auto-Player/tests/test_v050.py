import unittest
from pathlib import Path

from app.audio_note_cleanup import _limit_polyphony, basic_pitch_args, preset_for


class V050OnsetAnchoredCleanupTests(unittest.TestCase):
    def test_rhythm_clean_disables_residual_energy_recovery(self):
        args = basic_pitch_args(preset_for("rhythm_clean"))
        self.assertIn("--no-melodia", args)
        self.assertIn("--minimum-note-length", args)
        floor_index = args.index("--minimum-note-length") + 1
        self.assertEqual(args[floor_index], "55.0")

    def test_maximum_sensitivity_mode_keeps_melodia(self):
        args = basic_pitch_args(preset_for("rhythm"))
        self.assertNotIn("--no-melodia", args)

    def test_rhythm_clean_caps_onset_cluster_to_five_notes(self):
        self.assertEqual(preset_for("rhythm_clean").max_chord_notes, 5)

    def test_polyphony_pruning_does_not_force_weak_extremes(self):
        cluster = [
            (0.0, 80.0, 36, 23),   # weak low outlier
            (0.0, 150.0, 60, 90),
            (0.0, 140.0, 64, 82),
            (0.0, 130.0, 67, 78),
            (0.0, 120.0, 72, 74),
            (0.0, 110.0, 76, 70),
            (0.0, 100.0, 79, 68),
            (0.0, 70.0, 108, 22),  # weak high outlier
        ]
        kept, dropped = _limit_polyphony(cluster, 6)
        pitches = [note[2] for note in kept]
        self.assertEqual(dropped, 2)
        self.assertNotIn(36, pitches)
        self.assertNotIn(108, pitches)
        self.assertEqual(pitches, [60, 64, 67, 72, 76, 79])

    def test_ui_versions_and_line_cap(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        server = Path("app/server.py").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v", html)
        self.assertIn("Piano Auto Player v", server)
        self.assertIn("onset-anchored", html)
        for name in [
            "app/audio_ghost_filter.py", "app/audio_note_cleanup.py", "app/audio_transcriber.py",
            "app/performance_lifecycle.py", "app/performance_notes.py", "app/playback.py",
            "app/server.py", "web/youtube_piano.js", "web/app.js",
        ]:
            lines = len(Path(name).read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(lines, 450, f"{name} exceeded 450 lines ({lines})")


if __name__ == "__main__":
    unittest.main()
