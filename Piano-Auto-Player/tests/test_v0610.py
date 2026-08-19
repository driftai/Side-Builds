import unittest
from pathlib import Path

from app.hifi_piano import HifiFusionConfig, _coherent_timing_adjustments, fuse_piano_models
from app.hifi_sustain import stitch_consensus_sustain

ROOT = Path(__file__).resolve().parents[1]


class V0610AdaptiveContinuityTimingTests(unittest.TestCase):
    def test_one_neighboring_attack_no_longer_overrides_same_origin_hold(self):
        specialist = [
            (100.0, 300.0, 61, 70), (326.0, 510.0, 61, 72),
            (326.0, 500.0, 64, 76),
        ]
        basic = [(104.0, 520.0, 61, 68), (331.0, 505.0, 64, 73)]
        fixed, stats = stitch_consensus_sustain(specialist, specialist, basic)
        self.assertEqual(len([note for note in fixed if note[2] == 61]), 1)
        self.assertEqual(stats["hifi_sustain_weak_context_stitches"], 1)
        self.assertEqual(stats["hifi_sustain_context_reattacks_protected"], 0)

    def test_two_confirmed_neighboring_tones_still_protect_repeated_chord(self):
        specialist = [
            (100.0, 300.0, 61, 70), (326.0, 510.0, 61, 72),
            (326.0, 500.0, 64, 76), (329.0, 505.0, 68, 74),
        ]
        basic = [
            (104.0, 520.0, 61, 68), (331.0, 505.0, 64, 73),
            (333.0, 510.0, 68, 70),
        ]
        fixed, stats = stitch_consensus_sustain(specialist, specialist, basic)
        self.assertEqual(len([note for note in fixed if note[2] == 61]), 2)
        self.assertEqual(stats["hifi_sustain_context_reattacks_protected"], 1)

    def test_pedal_origin_guard_remains_strict(self):
        specialist = [(500.0, 690.0, 61, 66), (720.0, 900.0, 61, 68)]
        basic = [(105.0, 950.0, 61, 70)]
        fixed, stats = stitch_consensus_sustain(specialist, specialist, basic)
        self.assertEqual(len(fixed), 2)
        self.assertEqual(stats["hifi_sustain_pedal_reattacks_protected"], 1)

    def test_timing_fusion_moves_a_chord_as_one_cluster(self):
        notes = [(100.0, 300.0, 60, 70), (113.0, 310.0, 64, 72)]
        matches = {0: (0, (155.0, 320.0, 60, 68)), 1: (1, (58.0, 280.0, 64, 69))}
        adjustments, stats = _coherent_timing_adjustments(notes, matches, HifiFusionConfig())
        self.assertAlmostEqual(adjustments.get(0, 0.0), adjustments.get(1, 0.0), places=6)
        self.assertLessEqual(abs(adjustments.get(0, 0.0)), 4.0)
        self.assertEqual(stats["hifi_timing_notes_shifted"], 0)

    def test_large_shared_model_offset_is_capped_for_whole_chord(self):
        notes = [(100.0, 300.0, 60, 70), (110.0, 310.0, 64, 72)]
        matches = {0: (0, (140.0, 320.0, 60, 68)), 1: (1, (150.0, 330.0, 64, 69))}
        adjustments, stats = _coherent_timing_adjustments(notes, matches, HifiFusionConfig())
        self.assertEqual(adjustments[0], 4.0)
        self.assertEqual(adjustments[1], 4.0)
        self.assertEqual(stats["hifi_timing_adjustments_capped"], 1)

    def test_fusion_reports_new_timing_and_continuity_diagnostics(self):
        specialist = [(100.0, 300.0, 61, 70), (326.0, 510.0, 61, 72)]
        basic = [(104.0, 520.0, 61, 68)]
        _fixed, stats = fuse_piano_models(specialist, basic)
        self.assertIn("hifi_sustain_weak_context_stitches", stats)
        self.assertIn("hifi_timing_clusters_adjusted", stats)
        self.assertIn("hifi_timing_adjustments_capped", stats)

    def test_version_ui_diagnostics_and_line_caps(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "web" / "youtube_piano.js").read_text(encoding="utf-8")
        server = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v0.6.21", html)
        self.assertIn("PianoAutoPlayer/0.6.21", server)
        self.assertIn("weak-context holds restored", js)
        self.assertIn("timing clusters aligned", js)
        for path in [*Path(ROOT / "app").glob("*.py"), *Path(ROOT / "web").glob("*.js")]:
            self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 450, str(path))


if __name__ == "__main__":
    unittest.main()
