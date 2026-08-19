import unittest
from pathlib import Path

from app.hifi_piano import HifiFusionConfig, _coherent_timing_adjustments
from app.hifi_timing import RelativeTimingConfig, stabilize_cluster_shifts

ROOT = Path(__file__).resolve().parents[1]


class V0616RelativePacingContinuityTests(unittest.TestCase):
    def test_dense_neighbor_cannot_drop_from_large_delay_to_zero_in_one_step(self):
        stable, stats = stabilize_cluster_shifts([100.0, 150.0, 200.0], [18.0, 0.0, 0.0])
        self.assertEqual(stable[0], 18.0)
        self.assertGreaterEqual(stable[1], 15.0)
        self.assertGreaterEqual(stable[2], 12.0)
        self.assertGreaterEqual(stats["hifi_timing_relative_slew_limited"], 2)
        self.assertLessEqual(stats["hifi_timing_stable_max_step_ms"], 3.0)

    def test_fast_passage_gets_tighter_slew_than_slow_passage(self):
        cfg = RelativeTimingConfig()
        fast, _ = stabilize_cluster_shifts([100.0, 120.0], [15.0, 0.0], cfg)
        slow, _ = stabilize_cluster_shifts([100.0, 150.0], [15.0, 0.0], cfg)
        self.assertGreater(fast[1], slow[1])

    def test_phrase_gap_allows_fresh_timing_measurement(self):
        stable, stats = stabilize_cluster_shifts([100.0, 150.0, 400.0], [18.0, 0.0, 0.0])
        self.assertGreater(stable[1], 0.0)
        self.assertEqual(stable[2], 0.0)
        self.assertEqual(stats["hifi_timing_phrase_resets"], 1)

    def test_coherent_timing_smooths_acoustic_correction_into_next_attack(self):
        notes = [
            (100.0, 300.0, 60, 70), (104.0, 310.0, 64, 72),
            (160.0, 340.0, 67, 69), (164.0, 350.0, 71, 71),
        ]
        matches = {
            0: (0, (114.0, 300.0, 60, 68)), 1: (1, (118.0, 310.0, 64, 70)),
            2: (2, (160.0, 340.0, 67, 68)), 3: (3, (164.0, 350.0, 71, 70)),
        }
        adjustments, stats = _coherent_timing_adjustments(
            notes, matches, HifiFusionConfig(), acoustic_onsets=[(120.0, 0.90)]
        )
        first = adjustments[0]
        second = adjustments[2]
        self.assertGreater(first, 6.0)
        self.assertGreater(second, 0.0)
        self.assertLessEqual(abs(second - first), 3.0)
        self.assertGreaterEqual(stats["hifi_timing_relative_slew_limited"], 1)

    def test_zero_timing_corrections_remain_zero(self):
        stable, stats = stabilize_cluster_shifts([100.0, 150.0], [0.0, 0.0])
        self.assertEqual(stable, [0.0, 0.0])
        self.assertEqual(stats["hifi_timing_relative_slew_limited"], 0)

    def test_version_ui_diagnostics_and_line_caps(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "web" / "youtube_piano.js").read_text(encoding="utf-8")
        server = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v0.6.21", html)
        self.assertIn("PianoAutoPlayer/0.6.21", server)
        self.assertIn("relative timing jumps softened", js)
        self.assertIn("phrase timing resets", js)
        for path in [*Path(ROOT / "app").glob("*.py"), *Path(ROOT / "web").glob("*.js")]:
            self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 450, str(path))


if __name__ == "__main__":
    unittest.main()
