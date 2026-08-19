import unittest
from pathlib import Path

from app.hifi_timing import RelativeTimingConfig, stabilize_cluster_shifts

ROOT = Path(__file__).resolve().parents[1]


class V0619TextureBoundaryHysteresisTests(unittest.TestCase):
    def test_isolated_dense_blip_inside_sparse_run_does_not_reset_twice(self):
        stable, stats = stabilize_cluster_shifts(
            [100.0, 150.0, 200.0, 250.0, 300.0],
            [5.0, 4.5, -3.0, 4.0, 3.5],
            independent=[True, True, False, True, True],
        )
        self.assertEqual(stats["hifi_timing_texture_flicker_suppressed"], 1)
        self.assertEqual(stats["hifi_timing_sparse_resets"], 0)
        self.assertLessEqual(abs(stable[2] - stable[1]), 1.25)
        self.assertLessEqual(abs(stable[3] - stable[2]), 1.25)

    def test_isolated_sparse_blip_inside_dense_run_is_also_debounced(self):
        stable, stats = stabilize_cluster_shifts(
            [100.0, 150.0, 200.0, 250.0, 300.0],
            [2.0, 2.5, -4.0, 3.0, 3.5],
            independent=[False, False, True, False, False],
        )
        self.assertEqual(stats["hifi_timing_texture_flicker_suppressed"], 1)
        self.assertEqual(stats["hifi_timing_sparse_resets"], 0)
        self.assertLessEqual(abs(stable[2] - stable[1]), 3.0)

    def test_persistent_texture_transition_still_resets(self):
        _stable, stats = stabilize_cluster_shifts(
            [100.0, 150.0, 200.0, 250.0, 300.0],
            [5.0, 4.5, -3.0, -3.5, -4.0],
            independent=[True, True, False, False, False],
        )
        self.assertEqual(stats["hifi_timing_texture_flicker_suppressed"], 0)
        self.assertGreaterEqual(stats["hifi_timing_sparse_resets"], 1)

    def test_phrase_gap_prevents_flicker_collapse(self):
        cfg = RelativeTimingConfig(phrase_reset_ms=180.0)
        _stable, stats = stabilize_cluster_shifts(
            [100.0, 150.0, 400.0, 450.0, 500.0],
            [4.0, 4.0, -3.0, 4.0, 4.0],
            cfg, independent=[True, True, False, True, True],
        )
        self.assertEqual(stats["hifi_timing_texture_flicker_suppressed"], 0)
        self.assertGreaterEqual(stats["hifi_timing_sparse_resets"], 1)

    def test_rule_is_universal_not_song_or_event_hardcoded(self):
        source = (ROOT / "app" / "hifi_timing.py").read_text(encoding="utf-8")
        self.assertNotIn("Sparkle", source)
        self.assertNotIn("event 50", source.lower())
        self.assertNotIn("event 200", source.lower())
        self.assertNotIn("cKgnDmpb4BU", source)

    def test_version_ui_diagnostics_and_line_caps(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "web" / "youtube_piano.js").read_text(encoding="utf-8")
        server = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v0.6.21", html)
        self.assertIn("PianoAutoPlayer/0.6.21", server)
        self.assertIn("texture flicker resets suppressed", js)
        for path in [*Path(ROOT / "app").glob("*.py"), *Path(ROOT / "web").glob("*.js")]:
            self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 450, str(path))


if __name__ == "__main__":
    unittest.main()
