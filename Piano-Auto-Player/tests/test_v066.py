import tempfile
import unittest
from pathlib import Path

from app.hifi_piano import fuse_piano_models
from app.library import SongLibrary


ROOT = Path(__file__).resolve().parents[1]


class V066HifiConfidenceSensorTests(unittest.TestCase):
    def test_fusion_reports_bidirectional_coverage_and_onset_error(self):
        specialist = [(i * 1000.0, i * 1000.0 + 240.0, 60 + (i % 3), 88) for i in range(12)]
        basic = []
        for i, note in enumerate(specialist):
            pitch = note[2] if i < 6 else note[2] + 12
            basic.append((note[0] + 10.0, note[1] + 10.0, pitch, 72))
        _fused, stats = fuse_piano_models(specialist, basic)
        self.assertEqual(stats["hifi_model_agreements"], 6)
        self.assertEqual(stats["hifi_specialist_coverage"], 0.5)
        self.assertEqual(stats["hifi_basic_coverage"], 0.5)
        self.assertEqual(stats["hifi_onset_median_offset_ms"], 10.0)
        self.assertEqual(stats["hifi_onset_p95_abs_ms"], 10.0)
        self.assertEqual(stats["hifi_review_window_count"], 1)
        self.assertEqual(stats["hifi_worst_window_start_ms"], 5000)

    def test_sensor_metrics_remain_raw_when_timing_fusion_is_bounded(self):
        fused, stats = fuse_piano_models([(100.0, 300.0, 60, 80)], [(120.0, 320.0, 60, 70)])
        self.assertEqual(fused[0][0], 104.0)
        self.assertEqual(fused[0][1], 300.0)
        self.assertGreaterEqual(stats["hifi_attack_release_overhang_guarded"], 1)
        self.assertEqual(stats["hifi_onset_median_offset_ms"], 20.0)
        self.assertIn("hifi_windows", stats)
        self.assertEqual(stats["hifi_review_window_count"], 0)

    def test_library_preserves_transcription_diagnostics(self):
        diagnostics = {"hifi_agreement_f1": 0.6891, "hifi_windows": [{"start_ms": 0, "level": "strong"}]}
        with tempfile.TemporaryDirectory() as td:
            library = SongLibrary(Path(td) / "songs.json")
            saved = library.save({
                "title": "Sensor test",
                "performance": [{"key": "a", "at_ms": 0, "duration_ms": 80, "midi_notes": [60]}],
                "transcription_diagnostics": diagnostics,
            })
            self.assertEqual(saved["transcription_diagnostics"], diagnostics)
            self.assertEqual(library.list()[0]["transcription_diagnostics"], diagnostics)

    def test_frontend_exposes_precision_heatmap_and_raw_sensor_copy(self):
        js = (ROOT / "web" / "youtube_piano.js").read_text(encoding="utf-8")
        confidence = (ROOT / "web" / "hifi_confidence.js").read_text(encoding="utf-8")
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("toFixed(1)", js)
        self.assertIn("hifiConfidenceHeatmap", html)
        self.assertIn("raw model predictions", html)
        self.assertIn("Lowest-agreement regions", confidence)

    def test_current_version_and_source_line_caps(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        server = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v0.6.21", html)
        self.assertIn("PianoAutoPlayer/0.6.21", server)
        for path in [*Path(ROOT / "app").glob("*.py"), *Path(ROOT / "web").glob("*.js")]:
            self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 450, str(path))


if __name__ == "__main__":
    unittest.main()
