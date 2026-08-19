import unittest
from pathlib import Path

from app.hifi_piano import fuse_piano_models
from app.hifi_sustain import stitch_consensus_sustain

ROOT = Path(__file__).resolve().parents[1]


class V069PedalAwareReattackTests(unittest.TestCase):
    def test_long_pedal_hold_does_not_erase_later_specialist_reattack(self):
        specialist = [(500.0, 690.0, 61, 66), (720.0, 900.0, 61, 68)]
        basic = [(105.0, 950.0, 61, 70)]
        fixed, stats = stitch_consensus_sustain(specialist, specialist, basic)
        self.assertEqual(len([note for note in fixed if note[2] == 61]), 2)
        self.assertEqual(stats["hifi_sustain_stitches"], 0)
        self.assertEqual(stats["hifi_sustain_pedal_reattacks_protected"], 1)

    def test_single_neighbor_context_defers_to_same_origin_continuity(self):
        specialist = [
            (100.0, 300.0, 61, 70), (326.0, 510.0, 61, 72),
            (326.0, 500.0, 64, 76),
        ]
        basic = [
            (104.0, 520.0, 61, 68),
            (331.0, 505.0, 64, 73),
        ]
        fused, stats = fuse_piano_models(specialist, basic)
        self.assertEqual(len([note for note in fused if note[2] == 61]), 1)
        self.assertEqual(stats["hifi_sustain_stitches"], 1)
        self.assertEqual(stats["hifi_sustain_context_reattacks_protected"], 0)
        self.assertEqual(stats["hifi_sustain_weak_context_stitches"], 1)

    def test_isolated_false_split_still_stitches(self):
        specialist = [(100.0, 300.0, 61, 70), (326.0, 510.0, 61, 72)]
        basic = [(104.0, 520.0, 61, 68)]
        fused, stats = fuse_piano_models(specialist, basic)
        self.assertEqual(len([note for note in fused if note[2] == 61]), 1)
        self.assertEqual(stats["hifi_sustain_stitches"], 1)
        self.assertEqual(stats["hifi_sustain_context_reattacks_protected"], 0)
        self.assertEqual(stats["hifi_sustain_pedal_reattacks_protected"], 0)

    def test_version_ui_diagnostics_and_line_caps(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "web" / "youtube_piano.js").read_text(encoding="utf-8")
        server = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v0.6.21", html)
        self.assertIn("PianoAutoPlayer/0.6.21", server)
        self.assertIn("pedal-held reattacks protected", js)
        self.assertIn("chord-context reattacks protected", js)
        for path in [*Path(ROOT / "app").glob("*.py"), *Path(ROOT / "web").glob("*.js")]:
            self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 450, str(path))


if __name__ == "__main__":
    unittest.main()
