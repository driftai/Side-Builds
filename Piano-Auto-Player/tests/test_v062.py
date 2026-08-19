import unittest
from pathlib import Path

from app.audio_consensus import ConsensusConfig, merge_consensus_detections


class V062PrecisionConsensusTests(unittest.TestCase):
    def test_sensitive_recovery_note_needs_two_sided_repeat_hole(self):
        rows = [
            (1, "sensitive", (100.0, 280.0, 60, 50), 0.90, 0.80),
            (2, "primary", (104.0, 270.0, 60, 53), 0.90, 0.82),
            (3, "strict", (108.0, 260.0, 60, 56), 0.88, 0.83),
            (0, "recovery", (700.0, 830.0, 60, 37), 0.91, 0.72),
            (1, "sensitive", (704.0, 825.0, 60, 38), 0.90, 0.70),
            (1, "sensitive", (1300.0, 1500.0, 60, 49), 0.92, 0.84),
            (2, "primary", (1304.0, 1490.0, 60, 52), 0.91, 0.84),
            (3, "strict", (1308.0, 1480.0, 60, 55), 0.90, 0.85),
        ]
        notes, stats = merge_consensus_detections(rows, 4)
        starts = [round(note[0]) for note in notes if note[2] == 60]
        self.assertIn(704, starts)
        self.assertEqual(stats["consensus_precision_rescued_notes"], 1)

    def test_one_sided_repetition_does_not_rescue_sensitive_noise(self):
        rows = [
            (0, "recovery", (100.0, 210.0, 60, 40), 0.95, 0.90),
            (1, "sensitive", (104.0, 205.0, 60, 41), 0.94, 0.88),
            (1, "sensitive", (800.0, 1050.0, 60, 50), 0.92, 0.88),
            (2, "primary", (804.0, 1040.0, 60, 53), 0.91, 0.87),
            (3, "strict", (808.0, 1030.0, 60, 56), 0.90, 0.86),
        ]
        notes, stats = merge_consensus_detections(rows, 4)
        self.assertNotIn(104, [round(note[0]) for note in notes])
        self.assertEqual(stats["consensus_precision_rescued_notes"], 0)

    def test_recovery_only_note_never_becomes_playable(self):
        rows = [
            (0, "recovery", (400.0, 600.0, 67, 70), 1.0, 1.0),
            (1, "sensitive", (1000.0, 1200.0, 60, 50), 0.8, 0.8),
            (2, "primary", (1004.0, 1190.0, 60, 54), 0.8, 0.8),
        ]
        notes, stats = merge_consensus_detections(rows, 4)
        self.assertNotIn(67, [note[2] for note in notes])
        self.assertEqual(stats["consensus_precision_rescued_notes"], 0)

    def test_high_chroma_but_wrong_octave_can_be_pruned_by_cqt(self):
        rows = [
            (1, "sensitive", (500.0, 580.0, 84, 38), 0.92, 0.02),
            (2, "primary", (504.0, 575.0, 84, 40), 0.90, 0.03),
            (1, "sensitive", (900.0, 1120.0, 60, 52), 0.90, 0.85),
            (2, "primary", (904.0, 1110.0, 60, 55), 0.91, 0.86),
            (3, "strict", (908.0, 1100.0, 60, 58), 0.90, 0.87),
        ]
        notes, stats = merge_consensus_detections(rows, 4)
        self.assertNotIn(84, [note[2] for note in notes])
        self.assertEqual(stats["consensus_spectral_pruned_notes"], 1)

    def test_rescue_budget_prevents_low_threshold_note_explosion(self):
        rows = []
        # 100 stable notes establish a realistic core-consensus body.
        for i in range(100):
            start = i * 100.0
            pitch = 60 + (i % 5)
            for pass_index, name, velocity in [(1, "sensitive", 48), (2, "primary", 52), (3, "strict", 56)]:
                rows.append((pass_index, name, (start, start + 90.0, pitch, velocity), 0.9, 0.85))
        # Add many plausible-looking sensitive+recovery notes. Even if some become
        # eligible, auxiliary rescue must never add an unbounded second transcription.
        for i in range(120):
            start = 50.0 + i * 80.0
            pitch = 60 + (i % 5)
            rows.append((0, "recovery", (start, start + 90.0, pitch, 40), 0.95, 0.90))
            rows.append((1, "sensitive", (start + 2.0, start + 88.0, pitch, 41), 0.94, 0.89))
        _notes, stats = merge_consensus_detections(rows, 4, ConsensusConfig(rescue_fraction=0.05, rescue_absolute_cap=8))
        self.assertLessEqual(stats["consensus_precision_rescued_notes"], 8)
        self.assertGreaterEqual(stats["consensus_rescue_suppressed"], 0)

    def test_decoder_uses_octave_specific_cqt_and_single_inference(self):
        text = Path("app/basic_pitch_consensus.py").read_text(encoding="utf-8")
        self.assertEqual(text.count("run_inference(args.audio"), 1)
        self.assertIn("librosa.cqt", text)
        self.assertIn("n_bins=88", text)
        self.assertIn("_spectral_score", text)

    def test_ui_and_server_report_v062_precision_mode(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        js = Path("web/youtube_piano.js").read_text(encoding="utf-8")
        server = Path("app/server.py").read_text(encoding="utf-8")
        self.assertIn("Rhythm accurate — precision consensus", html)
        self.assertIn("precision rescue", js)
        self.assertIn("rescue candidates suppressed", js)
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
