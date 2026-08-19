import unittest
from pathlib import Path

from app.hifi_piano import HifiFusionConfig, _coherent_timing_adjustments
from app.hifi_sparse import rescue_sparse_attacks, sparse_cluster_timing
from app.hifi_timing import stabilize_cluster_shifts

ROOT = Path(__file__).resolve().parents[1]


class V0617SparsePassageFidelityTests(unittest.TestCase):
    def test_sparse_cluster_uses_conservative_quarter_weight_timing(self):
        notes = [
            (0.0, 120.0, 58, 66), (100.0, 220.0, 60, 70),
            (200.0, 320.0, 62, 68), (300.0, 420.0, 64, 69),
            (400.0, 520.0, 65, 67),
        ]
        matches = {1: (1, (120.0, 230.0, 60, 68))}
        sparse, shift = sparse_cluster_timing(notes, [1], matches)
        self.assertTrue(sparse)
        self.assertEqual(shift, 5.0)

    def test_sparse_cluster_bypasses_stronger_acoustic_delay(self):
        notes = [
            (0.0, 120.0, 58, 66), (100.0, 260.0, 60, 70),
            (200.0, 320.0, 62, 68), (300.0, 420.0, 64, 69),
            (400.0, 520.0, 65, 67),
        ]
        matches = {0: (0, (20.0, 130.0, 58, 68))}
        adjustments, stats = _coherent_timing_adjustments(
            notes, matches, HifiFusionConfig(), acoustic_onsets=[(24.0, 0.95)]
        )
        self.assertEqual(adjustments[0], 5.0)
        self.assertGreaterEqual(stats["hifi_sparse_timing_clusters"], 1)
        self.assertEqual(stats["hifi_sparse_acoustic_bypassed"], 1)

    def test_dense_chord_keeps_newer_acoustic_timing_path(self):
        notes = [
            (100.0, 280.0, 60, 70), (102.0, 282.0, 64, 70), (104.0, 284.0, 67, 70),
        ]
        matches = {
            0: (0, (116.0, 280.0, 60, 70)),
            1: (1, (118.0, 282.0, 64, 70)),
            2: (2, (120.0, 284.0, 67, 70)),
        }
        adjustments, stats = _coherent_timing_adjustments(
            notes, matches, HifiFusionConfig(), acoustic_onsets=[(122.0, 0.95)]
        )
        self.assertGreater(adjustments[0], 5.0)
        self.assertEqual(stats["hifi_sparse_timing_clusters"], 0)
        self.assertEqual(stats["hifi_acoustic_clusters_delayed"], 1)

    def test_sparse_missing_attack_requires_waveform_confirmation(self):
        basic = [(300.0, 430.0, 64, 62)]
        fused = [(80.0, 180.0, 60, 65), (560.0, 680.0, 67, 65)]
        rescued, stats = rescue_sparse_attacks(
            basic, set(), fused, acoustic_onsets=[(301.0, 0.82)]
        )
        self.assertEqual(rescued, basic)
        self.assertEqual(stats["hifi_sparse_attack_rescues"], 1)

        rejected, rejected_stats = rescue_sparse_attacks(
            basic, set(), fused, acoustic_onsets=[(301.0, 0.18)]
        )
        self.assertEqual(rejected, [])
        self.assertEqual(rejected_stats["hifi_sparse_attack_rescues"], 0)

    def test_sparse_boundary_does_not_inherit_dense_timing_shift(self):
        stable, stats = stabilize_cluster_shifts(
            [100.0, 150.0, 210.0], [16.0, 14.0, 1.0], independent=[False, False, True]
        )
        self.assertEqual(stable[-1], 1.0)
        self.assertGreaterEqual(stats["hifi_timing_sparse_resets"], 1)

    def test_patch_is_universal_not_song_or_event_hardcoded(self):
        source = (ROOT / "app" / "hifi_sparse.py").read_text(encoding="utf-8")
        self.assertNotIn("Sparkle", source)
        self.assertNotIn("cKgnDmpb4BU", source)

    def test_version_ui_diagnostics_and_line_caps(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "web" / "youtube_piano.js").read_text(encoding="utf-8")
        server = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v0.6.21", html)
        self.assertIn("PianoAutoPlayer/0.6.21", server)
        self.assertIn("sparse timing anchors", js)
        self.assertIn("sparse missing attacks rescued", js)
        for path in [*Path(ROOT / "app").glob("*.py"), *Path(ROOT / "web").glob("*.js")]:
            self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 450, str(path))


if __name__ == "__main__":
    unittest.main()
