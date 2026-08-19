import json
import tempfile
import unittest
from pathlib import Path

from app.audio_consensus import load_consensus_notes
from app.hifi_onset import AcousticPacingConfig, acoustic_pacing_delay
from app.hifi_piano import HifiFusionConfig, _coherent_timing_adjustments, fuse_piano_models

ROOT = Path(__file__).resolve().parents[1]


class V0612AcousticPacingGuardTests(unittest.TestCase):
    def test_dense_early_cluster_delays_toward_confirmed_audio_attack(self):
        notes = [
            (100.0, 300.0, 60, 70),
            (104.0, 310.0, 64, 72),
            (108.0, 320.0, 67, 68),
            (175.0, 350.0, 72, 64),
        ]
        matches = {
            0: (0, (114.0, 300.0, 60, 68)),
            1: (1, (118.0, 310.0, 64, 70)),
            2: (2, (121.0, 320.0, 67, 66)),
        }
        shift, reason = acoustic_pacing_delay(notes, [0, 1, 2], matches, [(120.0, 0.82)])
        self.assertGreaterEqual(shift, 8.0)
        self.assertLessEqual(shift, AcousticPacingConfig().maximum_delay_ms)
        self.assertEqual(reason, "dense")

    def test_acoustic_guard_never_pulls_cluster_earlier(self):
        notes = [(100.0, 300.0, 60, 70), (104.0, 310.0, 64, 72)]
        matches = {0: (0, (112.0, 300.0, 60, 68)), 1: (1, (116.0, 310.0, 64, 70))}
        shift, _reason = acoustic_pacing_delay(notes, [0, 1], matches, [(88.0, 0.95)])
        self.assertEqual(shift, 0.0)

    def test_waveform_peak_alone_cannot_move_model_without_later_basic_support(self):
        notes = [(100.0, 300.0, 60, 70), (104.0, 310.0, 64, 72)]
        matches = {0: (0, (98.0, 300.0, 60, 68)), 1: (1, (103.0, 310.0, 64, 70))}
        shift, _reason = acoustic_pacing_delay(notes, [0, 1], matches, [(120.0, 0.95)])
        self.assertEqual(shift, 0.0)

    def test_fusion_uses_acoustic_delay_as_later_only_override(self):
        specialist = [(100.0, 300.0, 60, 70), (103.0, 310.0, 64, 72)]
        basic = [(114.0, 305.0, 60, 68), (117.0, 315.0, 64, 70)]
        notes, stats = fuse_piano_models(specialist, basic, acoustic_onsets=[(120.0, 0.90)])
        self.assertGreater(min(note[0] for note in notes), 104.0)
        self.assertEqual(stats["hifi_acoustic_clusters_delayed"], 1)
        self.assertEqual(stats["hifi_acoustic_dense_delays"], 1)

    def test_no_acoustic_data_preserves_v0611_timing_behavior(self):
        notes = [(100.0, 300.0, 60, 70)]
        matches = {0: (0, (140.0, 310.0, 60, 69))}
        adjustments, stats = _coherent_timing_adjustments(notes, matches, HifiFusionConfig())
        self.assertEqual(adjustments[0], 4.0)
        self.assertEqual(stats["hifi_acoustic_clusters_delayed"], 0)

    def test_consensus_loader_keeps_acoustic_onsets_internal(self):
        payload = {
            "analysis": {"percussive_ratio": 0.2, "acoustic_onsets": [[120.0, 0.8], [240.0, 0.6]]},
            "passes": [
                {"name": "sensitive", "notes": [[100, 300, 60, 70, 0.8, 0.8]]},
                {"name": "primary", "notes": [[101, 301, 60, 70, 0.8, 0.8]]},
                {"name": "strict", "notes": [[102, 302, 60, 70, 0.8, 0.8]]},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "consensus.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            _notes, stats = load_consensus_notes(path)
        self.assertEqual(stats["_acoustic_onsets"], [(120.0, 0.8), (240.0, 0.6)])
        self.assertEqual(stats["acoustic_onset_peaks"], 2)

    def test_version_ui_and_line_caps(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "web" / "youtube_piano.js").read_text(encoding="utf-8")
        server = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v0.6.21", html)
        self.assertIn("PianoAutoPlayer/0.6.21", server)
        self.assertIn("acoustic onset corrections", js)
        self.assertIn("dense early attacks delayed", js)
        for path in [*Path(ROOT / "app").glob("*.py"), *Path(ROOT / "web").glob("*.js")]:
            self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 450, str(path))


if __name__ == "__main__":
    unittest.main()
