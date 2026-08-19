import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.audio_engine import transcribe_audio
from app.audio_note_cleanup import preset_for
from app.hifi_range import compact_specialist_for_layout


class V065RangeAwareHiFiTests(unittest.TestCase):
    def test_61_key_compacts_edge_register_instead_of_dropping(self):
        notes = [
            (0.0, 300.0, 24, 90),   # C1 -> C2
            (100.0, 400.0, 60, 80), # C4 stays C4
            (200.0, 500.0, 108, 75),# C8 -> C7
        ]
        out, stats = compact_specialist_for_layout(notes, "61")
        self.assertEqual([n[2] for n in out], [36, 60, 96])
        self.assertEqual(stats["hifi_range_compacted_notes"], 2)

    def test_88_key_preserves_exact_register(self):
        notes = [(0.0, 300.0, 24, 90), (200.0, 500.0, 108, 75)]
        out, stats = compact_specialist_for_layout(notes, "88")
        self.assertEqual(out, notes)
        self.assertEqual(stats["hifi_range_compacted_notes"], 0)

    def test_fold_collision_merges_not_double_presses(self):
        notes = [
            (100.0, 300.0, 24, 60),  # C1 -> C2
            (108.0, 420.0, 36, 91),  # existing C2 at same attack
        ]
        out, stats = compact_specialist_for_layout(notes, "61")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][2], 36)
        self.assertEqual(out[0][3], 91)
        self.assertAlmostEqual(out[0][1], 420.0)
        self.assertEqual(stats["hifi_range_collision_merges"], 1)

    def test_auto_hifi_61_compacts_before_model_fusion(self):
        basic = [(100.0, 280.0, 60, 62)]
        specialist = [(0.0, 260.0, 24, 85), (102.0, 290.0, 60, 80)]
        with tempfile.TemporaryDirectory() as td, \
             patch("app.audio_engine._basic_consensus", return_value=(basic, {"consensus_kept_notes": 1})), \
             patch("app.audio_engine._transkun_notes", return_value=specialist), \
             patch("app.audio_engine.auto_accept_specialist", return_value=True):
            perf, stats = transcribe_audio(
                lambda _cmd: None, "main-python", "basic-pitch", Path(td) / "audio.wav", Path(td),
                preset_for("rhythm_accurate"), "61", engine="auto_hifi", hifi_python="hifi-python", hifi_device="cpu",
            )
        self.assertEqual(stats["transcription_engine"], "hifi_fusion")
        self.assertEqual(stats["hifi_range_compacted_notes"], 1)
        self.assertEqual(stats["cleanup_layout_drops"], 0)
        all_midi = [m for event in perf for m in event["midi_notes"]]
        self.assertIn(36, all_midi)

    def test_current_version_ui_and_line_caps(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        js = Path("web/youtube_piano.js").read_text(encoding="utf-8")
        server = Path("app/server.py").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v0.6.21", html)
        self.assertIn("PianoAutoPlayer/0.6.21", server)
        self.assertIn("61-key edge notes compacted", js)
        for path in [*Path("app").glob("*.py"), *Path("web").glob("*.js")]:
            self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 450, str(path))


if __name__ == "__main__":
    unittest.main()
