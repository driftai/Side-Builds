import unittest
from pathlib import Path

from app.hifi_sustain import stitch_consensus_sustain

ROOT = Path(__file__).resolve().parents[1]


class V0614AcousticReattackArbiterTests(unittest.TestCase):
    def test_continuous_second_model_stitches_false_same_key_jump(self):
        specialist = [(100.0, 200.0, 61, 70), (220.0, 330.0, 61, 68)]
        basic = [(101.0, 332.0, 61, 69)]
        notes, stats = stitch_consensus_sustain(specialist, specialist, basic, acoustic_onsets=[])
        self.assertEqual(len([n for n in notes if n[2] == 61]), 1)
        self.assertEqual(stats["hifi_sustain_continuity_stitches"], 1)

    def test_acoustic_peak_protects_real_reattack_against_continuity_vote(self):
        specialist = [(100.0, 200.0, 61, 70), (220.0, 330.0, 61, 68)]
        basic = [(101.0, 332.0, 61, 69)]
        notes, stats = stitch_consensus_sustain(
            specialist, specialist, basic, acoustic_onsets=[(222.0, 0.82)]
        )
        self.assertEqual(len([n for n in notes if n[2] == 61]), 2)
        self.assertEqual(stats["hifi_sustain_acoustic_reattacks_protected"], 1)

    def test_dual_model_same_pitch_onset_still_hard_protects_reattack(self):
        specialist = [(100.0, 200.0, 61, 70), (220.0, 330.0, 61, 68)]
        basic = [(101.0, 205.0, 61, 69), (221.0, 331.0, 61, 67)]
        notes, stats = stitch_consensus_sustain(specialist, specialist, basic, acoustic_onsets=[])
        self.assertEqual(len([n for n in notes if n[2] == 61]), 2)
        self.assertGreaterEqual(stats["hifi_sustain_reattacks_protected"], 1)

    def test_tiny_unsupported_gap_is_deglitched_without_acoustic_attack(self):
        fused = [(100.0, 200.0, 64, 70), (216.0, 300.0, 64, 73)]
        specialist = [(100.0, 200.0, 64, 70), (216.0, 300.0, 64, 73)]
        basic = [(100.0, 198.0, 64, 69)]
        notes, stats = stitch_consensus_sustain(fused, specialist, basic, acoustic_onsets=[])
        self.assertEqual(len([n for n in notes if n[2] == 64]), 1)
        self.assertEqual(stats["hifi_sustain_microgap_stitches"], 1)

    def test_micro_gap_is_not_joined_when_waveform_has_attack(self):
        fused = [(100.0, 200.0, 64, 70), (216.0, 300.0, 64, 73)]
        specialist = [(100.0, 200.0, 64, 70), (216.0, 300.0, 64, 73)]
        basic = [(100.0, 198.0, 64, 69)]
        notes, stats = stitch_consensus_sustain(
            fused, specialist, basic, acoustic_onsets=[(214.0, 0.75)]
        )
        self.assertEqual(len([n for n in notes if n[2] == 64]), 2)
        self.assertEqual(stats["hifi_sustain_microgap_stitches"], 0)

    def test_version_ui_diagnostics_and_line_caps(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "web" / "youtube_piano.js").read_text(encoding="utf-8")
        server = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v0.6.21", html)
        self.assertIn("PianoAutoPlayer/0.6.21", server)
        self.assertIn("acoustic reattacks protected", js)
        self.assertIn("continuity jumps suppressed", js)
        self.assertIn("micro-gap jumps suppressed", js)
        for path in [*Path(ROOT / "app").glob("*.py"), *Path(ROOT / "web").glob("*.js")]:
            self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 450, str(path))


if __name__ == "__main__":
    unittest.main()
