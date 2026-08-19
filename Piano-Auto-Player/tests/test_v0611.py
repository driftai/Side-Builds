import unittest
from pathlib import Path

from app.hifi_piano import HifiFusionConfig, _blend, _coherent_timing_adjustments, fuse_piano_models

ROOT = Path(__file__).resolve().parents[1]


class V0611SustainWeightedPacingTests(unittest.TestCase):
    def test_secondary_short_interval_cannot_rush_specialist_release(self):
        stats = {}
        note = _blend((100.0, 500.0, 60, 72), (103.0, 320.0, 60, 68), HifiFusionConfig(), 0.0, stats)
        self.assertEqual(note[1], 500.0)
        self.assertEqual(stats["hifi_release_secondary_shorter_ignored"], 1)
        self.assertEqual(stats.get("hifi_release_secondary_tails_ignored", 0), 0)

    def test_secondary_longer_interval_cannot_extend_specialist_release(self):
        stats = {}
        note = _blend((100.0, 300.0, 60, 72), (103.0, 500.0, 60, 68), HifiFusionConfig(), 0.0, stats)
        self.assertEqual(note[1], 300.0)
        self.assertEqual(stats["hifi_release_secondary_tails_ignored"], 1)

    def test_large_pedal_tail_is_ignored_as_release_authority(self):
        stats = {}
        note = _blend((100.0, 300.0, 60, 72), (102.0, 1400.0, 60, 68), HifiFusionConfig(), 0.0, stats)
        self.assertEqual(note[1], 300.0)
        self.assertEqual(stats["hifi_release_secondary_tails_ignored"], 1)

    def test_small_onset_disagreement_is_ignored(self):
        notes = [(100.0, 300.0, 60, 70)]
        matches = {0: (0, (106.0, 310.0, 60, 69))}
        adjustments, stats = _coherent_timing_adjustments(notes, matches, HifiFusionConfig())
        self.assertEqual(adjustments, {})
        self.assertEqual(stats["hifi_timing_clusters_adjusted"], 0)

    def test_early_cross_model_pull_is_limited_to_one_ms(self):
        notes = [(100.0, 300.0, 60, 70)]
        matches = {0: (0, (60.0, 310.0, 60, 69))}
        adjustments, stats = _coherent_timing_adjustments(notes, matches, HifiFusionConfig())
        self.assertEqual(adjustments[0], -1.0)
        self.assertEqual(stats["hifi_timing_early_shifts_guarded"], 1)

    def test_later_cross_model_correction_keeps_four_ms_ceiling(self):
        notes = [(100.0, 300.0, 60, 70)]
        matches = {0: (0, (140.0, 310.0, 60, 69))}
        adjustments, _stats = _coherent_timing_adjustments(notes, matches, HifiFusionConfig())
        self.assertEqual(adjustments[0], 4.0)

    def test_fusion_reports_pacing_guard_diagnostics(self):
        specialist = [(100.0, 500.0, 60, 70), (800.0, 1000.0, 64, 72)]
        basic = [(102.0, 320.0, 60, 69), (804.0, 1120.0, 64, 70)]
        _notes, stats = fuse_piano_models(specialist, basic)
        self.assertEqual(stats["hifi_release_secondary_shorter_ignored"], 1)
        self.assertEqual(stats["hifi_release_secondary_tails_ignored"], 1)
        self.assertIn("hifi_timing_early_shifts_guarded", stats)

    def test_version_ui_diagnostics_and_line_caps(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "web" / "youtube_piano.js").read_text(encoding="utf-8")
        server = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v0.6.21", html)
        self.assertIn("PianoAutoPlayer/0.6.21", server)
        self.assertIn("early timing pulls guarded", js)
        self.assertIn("secondary early releases ignored", js)
        self.assertIn("secondary pedal tails ignored", js)
        for path in [*Path(ROOT / "app").glob("*.py"), *Path(ROOT / "web").glob("*.js")]:
            self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 450, str(path))


if __name__ == "__main__":
    unittest.main()
