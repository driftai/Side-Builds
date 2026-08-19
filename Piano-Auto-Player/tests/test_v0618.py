import unittest
from pathlib import Path

from app.hifi_timing import RelativeTimingConfig, stabilize_cluster_shifts

ROOT = Path(__file__).resolve().parents[1]


class V0618SparseTimingContinuityTests(unittest.TestCase):
    def test_consecutive_sparse_attacks_cannot_jump_between_offsets(self):
        stable, stats = stabilize_cluster_shifts(
            [100.0, 145.0, 190.0, 235.0],
            [5.0, -4.0, 5.0, -4.0],
            independent=[True, True, True, True],
        )
        self.assertLessEqual(abs(stable[1] - stable[0]), 1.25)
        self.assertLessEqual(abs(stable[2] - stable[1]), 1.25)
        self.assertLessEqual(abs(stable[3] - stable[2]), 1.25)
        self.assertGreaterEqual(stats["hifi_timing_sparse_slew_limited"], 2)
        self.assertEqual(stats["hifi_timing_sparse_resets"], 0)

    def test_sparse_texture_boundary_can_still_reset(self):
        stable, stats = stabilize_cluster_shifts(
            [100.0, 145.0, 190.0], [14.0, 12.0, 1.0],
            independent=[False, False, True],
        )
        self.assertEqual(stable[-1], 1.0)
        self.assertEqual(stats["hifi_timing_sparse_resets"], 1)

    def test_sparse_phrase_gap_can_reset_without_dragging_old_bias(self):
        cfg = RelativeTimingConfig(phrase_reset_ms=180.0)
        stable, stats = stabilize_cluster_shifts(
            [100.0, 145.0, 400.0], [5.0, 0.0, -3.0], cfg,
            independent=[True, True, True],
        )
        self.assertGreater(stable[1], 0.0)
        self.assertEqual(stable[2], -3.0)
        self.assertEqual(stats["hifi_timing_phrase_resets"], 1)

    def test_dense_lane_keeps_existing_v0616_limits(self):
        stable, stats = stabilize_cluster_shifts(
            [100.0, 150.0, 200.0], [18.0, 0.0, 0.0],
            independent=[False, False, False],
        )
        self.assertGreaterEqual(stable[1], 15.0)
        self.assertGreaterEqual(stable[2], 12.0)
        self.assertEqual(stats["hifi_timing_sparse_slew_limited"], 0)

    def test_patch_is_texture_driven_not_song_or_event_hardcoded(self):
        source = (ROOT / "app" / "hifi_timing.py").read_text(encoding="utf-8")
        self.assertNotIn("Sparkle", source)
        self.assertNotIn("event 25", source.lower())
        self.assertNotIn("cKgnDmpb4BU", source)

    def test_version_ui_diagnostics_and_line_caps(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "web" / "youtube_piano.js").read_text(encoding="utf-8")
        server = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v0.6.21", html)
        self.assertIn("PianoAutoPlayer/0.6.21", server)
        self.assertIn("sparse timing jumps softened", js)
        for path in [*Path(ROOT / "app").glob("*.py"), *Path(ROOT / "web").glob("*.js")]:
            self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 450, str(path))


if __name__ == "__main__":
    unittest.main()
