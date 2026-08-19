import json
import tempfile
import unittest
from pathlib import Path

from app.audio_consensus import merge_consensus_detections, load_consensus_notes


class V061TonalConsensusTests(unittest.TestCase):
    def test_recovery_note_is_rescued_by_repetition_and_tonal_support(self):
        rows = [
            (1, "sensitive", (100.0, 300.0, 60, 48), 0.91),
            (2, "primary", (104.0, 295.0, 60, 51), 0.90),
            (3, "strict", (108.0, 280.0, 60, 54), 0.89),
            # Weak C fills a repeated-note hole between two strong C attacks.
            (0, "recovery", (700.0, 830.0, 60, 36), 0.90),
            (1, "sensitive", (705.0, 825.0, 60, 37), 0.88),
            (1, "sensitive", (1300.0, 1500.0, 60, 47), 0.92),
            (2, "primary", (1304.0, 1490.0, 60, 50), 0.91),
            (3, "strict", (1307.0, 1480.0, 60, 53), 0.90),
        ]
        notes, stats = merge_consensus_detections(rows, 4)
        starts = [round(note[0]) for note in notes if note[2] == 60]
        self.assertIn(705, starts)
        self.assertEqual(stats["consensus_context_rescued_notes"], 1)

    def test_weak_two_pass_percussive_outlier_can_be_pruned(self):
        rows = [
            (1, "sensitive", (100.0, 350.0, 60, 52), 0.85),
            (2, "primary", (104.0, 340.0, 60, 55), 0.86),
            (3, "strict", (107.0, 330.0, 60, 58), 0.84),
            (1, "sensitive", (430.0, 500.0, 81, 36), 0.05),
            (2, "primary", (434.0, 498.0, 81, 38), 0.06),
            (1, "sensitive", (800.0, 1050.0, 64, 50), 0.81),
            (2, "primary", (804.0, 1040.0, 64, 53), 0.82),
            (3, "strict", (808.0, 1030.0, 64, 56), 0.80),
        ]
        notes, stats = merge_consensus_detections(rows, 4)
        self.assertNotIn(81, [note[2] for note in notes])
        self.assertEqual(stats["consensus_tonal_pruned_notes"], 1)

    def test_all_three_core_passes_survive_even_with_low_tonal_score(self):
        rows = [
            (1, "sensitive", (200.0, 300.0, 66, 40), 0.03),
            (2, "primary", (204.0, 295.0, 66, 44), 0.04),
            (3, "strict", (207.0, 290.0, 66, 48), 0.05),
        ]
        notes, stats = merge_consensus_detections(rows, 4)
        self.assertEqual([note[2] for note in notes], [66])
        self.assertEqual(stats["consensus_tonal_pruned_notes"], 0)

    def test_schema_two_loader_keeps_analysis_stats(self):
        payload = {
            "schema": 2,
            "analysis": {"percussive_ratio": 0.37, "tonal_profile": "hpss_chroma"},
            "passes": [
                {"name": "recovery", "notes": [[100, 400, 60, 40, 0.8]]},
                {"name": "sensitive", "notes": [[102, 390, 60, 44, 0.8]]},
                {"name": "primary", "notes": [[104, 380, 60, 48, 0.8]]},
                {"name": "strict", "notes": [[106, 370, 60, 52, 0.8]]},
            ],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(payload, handle)
            path = Path(handle.name)
        try:
            notes, stats = load_consensus_notes(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual([note[2] for note in notes], [60])
        self.assertEqual(stats["consensus_percussive_ratio"], 0.37)

    def test_helper_has_auxiliary_recovery_and_harmonic_profile(self):
        text = Path("app/basic_pitch_consensus.py").read_text(encoding="utf-8")
        self.assertEqual(text.count("run_inference(args.audio"), 1)
        self.assertIn('(\"recovery\", 0.405, 0.235)', text)
        self.assertIn("librosa.effects.hpss", text)
        self.assertIn("chroma_stft", text)

    def test_ui_reports_tonal_context_and_v061(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        js = Path("web/youtube_piano.js").read_text(encoding="utf-8")
        server = Path("app/server.py").read_text(encoding="utf-8")
        self.assertIn("Rhythm accurate — precision consensus", html)
        self.assertIn("precision rescue", js)
        self.assertIn("spectral guard removed", js)
        self.assertIn("Piano Auto Player v0.6.21", html)
        self.assertIn("PianoAutoPlayer/0.6.21", server)

    def test_line_cap(self):
        for name in [
            "app/basic_pitch_consensus.py", "app/audio_consensus.py", "app/audio_note_cleanup.py",
            "web/youtube_piano.js", "web/app.js",
        ]:
            lines = len(Path(name).read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(lines, 450, f"{name}: {lines}")


if __name__ == "__main__":
    unittest.main()
