import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.audio_engine import transcribe_audio
from app.audio_note_cleanup import preset_for
from app.hifi_piano import fuse_piano_models
from app.hifi_refine import refine_model_disagreements

ROOT = Path(__file__).resolve().parents[1]


class V067SourceSpacePrecisionTests(unittest.TestCase):
    def test_dense_chord_single_adjacent_mispitch_is_corrected(self):
        specialist = [
            (100.0, 300.0, 60, 80),
            (101.0, 300.0, 64, 78),
            (102.0, 260.0, 68, 46),  # G# suspect
        ]
        basic = [
            (105.0, 305.0, 60, 72),
            (105.0, 305.0, 64, 70),
            (106.0, 290.0, 67, 68),  # G supported by second model
        ]
        refined, stats = refine_model_disagreements(specialist, basic)
        self.assertEqual(stats["hifi_pitch_corrections"], 1)
        self.assertEqual({note[2] for note in refined}, {60, 64, 67})

    def test_two_note_chord_disagreement_remains_specialist_primary(self):
        specialist = [(100.0, 300.0, 60, 80), (101.0, 300.0, 64, 78)]
        basic = [(105.0, 305.0, 60, 72), (106.0, 290.0, 65, 68)]
        refined, stats = refine_model_disagreements(specialist, basic)
        self.assertEqual(stats["hifi_pitch_corrections"], 0)
        self.assertEqual({note[2] for note in refined}, {60, 64})

    def test_weak_short_extra_tone_in_confirmed_chord_can_be_removed(self):
        specialist = [
            (100.0, 300.0, 60, 80), (100.0, 300.0, 64, 80),
            (100.0, 300.0, 67, 80), (101.0, 190.0, 70, 45),
        ]
        basic = [(104.0, 300.0, 60, 70), (104.0, 300.0, 64, 70), (104.0, 300.0, 67, 70)]
        refined, stats = refine_model_disagreements(specialist, basic)
        self.assertEqual(stats["hifi_precision_pruned_notes"], 1)
        self.assertEqual({note[2] for note in refined}, {60, 64, 67})

    def test_repeated_extra_tone_is_protected(self):
        specialist = [
            (100.0, 300.0, 60, 80), (100.0, 300.0, 64, 80),
            (100.0, 300.0, 67, 80), (101.0, 190.0, 70, 45),
            (700.0, 820.0, 70, 46),
        ]
        basic = [(104.0, 300.0, 60, 70), (104.0, 300.0, 64, 70), (104.0, 300.0, 67, 70)]
        refined, stats = refine_model_disagreements(specialist, basic)
        self.assertEqual(stats["hifi_precision_pruned_notes"], 0)
        self.assertIn(70, [note[2] for note in refined])

    def test_raw_sensor_agreement_stays_raw_while_refinement_changes_output(self):
        specialist = [(100.0, 300.0, 60, 80), (101.0, 300.0, 64, 78), (102.0, 260.0, 68, 46)]
        basic = [(105.0, 305.0, 60, 72), (105.0, 305.0, 64, 70), (106.0, 290.0, 67, 68)]
        fused, stats = fuse_piano_models(specialist, basic)
        self.assertEqual(stats["hifi_model_agreements"], 2)
        self.assertEqual(stats["hifi_refined_model_agreements"], 3)
        self.assertEqual(stats["hifi_pitch_corrections"], 1)
        self.assertIn(67, [note[2] for note in fused])
        self.assertNotIn(68, [note[2] for note in fused])

    def test_auto_hifi_61_runs_basic_in_88_source_space_then_compacts_output(self):
        basic = [(100.0, 300.0, 24, 70), (500.0, 700.0, 60, 70)]
        specialist = [(102.0, 310.0, 24, 82), (502.0, 710.0, 60, 82)]
        with tempfile.TemporaryDirectory() as td, \
             patch("app.audio_engine._basic_consensus", return_value=(basic, {"consensus_kept_notes": 2})) as consensus, \
             patch("app.audio_engine._transkun_notes", return_value=specialist), \
             patch("app.audio_engine.auto_accept_specialist", return_value=True):
            perf, stats = transcribe_audio(
                lambda _cmd: None, "main-python", "basic-pitch", Path(td) / "audio.wav", Path(td),
                preset_for("rhythm_accurate"), "61", engine="auto_hifi", hifi_python="hifi-python", hifi_device="cpu",
            )
        self.assertEqual(consensus.call_args.args[-1], "88")
        self.assertEqual(stats["hifi_source_space_layout"], "88")
        self.assertEqual(stats["hifi_route"], "source_space_consensus")
        self.assertGreaterEqual(stats["hifi_range_compacted_notes"], 1)
        all_midi = [m for event in perf for m in event["midi_notes"]]
        self.assertIn(36, all_midi)
        self.assertNotIn(24, all_midi)

    def test_version_ui_and_line_caps(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "web" / "youtube_piano.js").read_text(encoding="utf-8")
        server = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v0.6.21", html)
        self.assertIn("PianoAutoPlayer/0.6.21", server)
        self.assertIn("precision pitch corrections", js)
        self.assertIn("88-key source space", html)
        for path in [*Path(ROOT / "app").glob("*.py"), *Path(ROOT / "web").glob("*.js")]:
            self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 450, str(path))


if __name__ == "__main__":
    unittest.main()
