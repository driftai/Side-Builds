import unittest
from pathlib import Path

from app.hifi_piano import fuse_piano_models
from app.hifi_sustain import stitch_consensus_sustain

ROOT = Path(__file__).resolve().parents[1]


class V068SustainContinuityTests(unittest.TestCase):
    def test_black_key_false_split_is_stitched_when_basic_hears_one_hold(self):
        specialist = [(100.0, 300.0, 61, 70), (326.0, 510.0, 61, 72)]
        basic = [(104.0, 520.0, 61, 68)]
        fused, stats = fuse_piano_models(specialist, basic)
        notes = [note for note in fused if note[2] == 61]
        self.assertEqual(len(notes), 1)
        self.assertGreaterEqual(notes[0][1], 510.0)
        self.assertEqual(stats["hifi_sustain_stitches"], 1)

    def test_white_key_false_split_uses_same_universal_rule(self):
        specialist = [(100.0, 280.0, 60, 70), (310.0, 490.0, 60, 71)]
        basic = [(101.0, 500.0, 60, 69)]
        fixed, stats = stitch_consensus_sustain(specialist, specialist, basic)
        self.assertEqual(len(fixed), 1)
        self.assertEqual(stats["hifi_sustain_stitches"], 1)

    def test_repeated_attack_is_kept_when_both_models_hear_second_onset(self):
        specialist = [(100.0, 300.0, 61, 70), (325.0, 500.0, 61, 73)]
        basic = [(104.0, 290.0, 61, 68), (329.0, 505.0, 61, 70)]
        fused, stats = fuse_piano_models(specialist, basic)
        self.assertEqual(len([note for note in fused if note[2] == 61]), 2)
        self.assertEqual(stats["hifi_sustain_stitches"], 0)
        self.assertGreaterEqual(stats["hifi_sustain_reattacks_protected"], 1)

    def test_strong_velocity_reattack_is_not_erased_by_one_model_hold(self):
        source = [(100.0, 300.0, 61, 52), (325.0, 500.0, 61, 82)]
        other = [(103.0, 510.0, 61, 68)]
        fixed, stats = stitch_consensus_sustain(source, source, other)
        self.assertEqual(len(fixed), 2)
        self.assertEqual(stats["hifi_sustain_stitches"], 0)
        self.assertEqual(stats["hifi_sustain_reattacks_protected"], 1)

    def test_version_ui_diagnostics_and_line_caps(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "web" / "youtube_piano.js").read_text(encoding="utf-8")
        server = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v0.6.21", html)
        self.assertIn("PianoAutoPlayer/0.6.21", server)
        self.assertIn("held-note stitches", js)
        self.assertIn("confirmed reattacks protected", js)
        for path in [*Path(ROOT / "app").glob("*.py"), *Path(ROOT / "web").glob("*.js")]:
            self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 450, str(path))


if __name__ == "__main__":
    unittest.main()
