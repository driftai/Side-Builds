import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.audio_consensus import merge_consensus_detections, load_consensus_notes
from app.audio_note_cleanup import performance_from_notes, preset_for
from app.youtube_access import load_saved_session, saved_session_path, youtube_attempts


class V059AccuracyConsensusTests(unittest.TestCase):
    def test_consensus_keeps_two_pass_note_and_rejects_single_noise(self):
        rows = [
            (0, "sensitive", (100.0, 420.0, 60, 44)),
            (1, "primary", (106.0, 408.0, 60, 47)),
            (2, "strict", (103.0, 395.0, 60, 50)),
            (0, "sensitive", (220.0, 275.0, 73, 31)),
        ]
        notes, stats = merge_consensus_detections(rows, 3)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0][2], 60)
        self.assertEqual(stats["consensus_rejected_notes"], 1)
        self.assertEqual(stats["consensus_all_pass_notes"], 1)

    def test_consensus_preserves_confident_primary_only_attack(self):
        rows = [(1, "primary", (500.0, 710.0, 67, 72))]
        notes, stats = merge_consensus_detections(rows, 3)
        self.assertEqual([note[2] for note in notes], [67])
        self.assertEqual(stats["consensus_strong_single_notes"], 1)

    def test_consensus_uses_median_timing(self):
        rows = [
            (0, "sensitive", (990.0, 1510.0, 64, 40)),
            (1, "primary", (1000.0, 1490.0, 64, 46)),
            (2, "strict", (1008.0, 1460.0, 64, 52)),
        ]
        notes, _stats = merge_consensus_detections(rows, 3)
        self.assertEqual(notes[0][:3], (1000.0, 1490.0, 64))
        self.assertEqual(notes[0][3], 46)

    def test_json_loader_and_existing_cleanup_pipeline(self):
        payload = {"schema": 1, "passes": [
            {"name": "sensitive", "notes": [[100, 500, 60, 45], [300, 360, 79, 30]]},
            {"name": "primary", "notes": [[104, 490, 60, 48]]},
            {"name": "strict", "notes": [[102, 480, 60, 51]]},
        ]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(payload, handle); path = Path(handle.name)
        try:
            notes, consensus = load_consensus_notes(path)
            performance, stats = performance_from_notes(notes, preset_for("rhythm_accurate"), "61", consensus)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(len(performance), 1)
        self.assertEqual(stats["consensus_rejected_notes"], 1)
        self.assertEqual(stats["transcription_quality"], "rhythm_accurate")

    def test_helper_runs_one_inference_then_multiple_decodes_by_construction(self):
        text = Path("app/basic_pitch_consensus.py").read_text(encoding="utf-8")
        self.assertEqual(text.count("run_inference(args.audio"), 1)
        self.assertIn("0.455", text)
        self.assertIn("0.555", text)
        self.assertIn("model_output_to_notes", text)

    def test_ui_and_runtime_default_to_accuracy_mode(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        api = Path("web/api.js").read_text(encoding="utf-8")
        server = Path("app/server.py").read_text(encoding="utf-8")
        self.assertIn("Rhythm accurate — precision consensus", html)
        self.assertIn('quality = "rhythm_accurate"', api)
        self.assertIn("Piano Auto Player v0.6.21", html)
        self.assertIn("PianoAutoPlayer/0.6.21", server)

    def test_explicit_anonymous_ignores_saved_session(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write("# Netscape HTTP Cookie File\n")
            cookie_path = Path(handle.name)
        try:
            attempts = youtube_attempts("anonymous", str(cookie_path))
        finally:
            cookie_path.unlink(missing_ok=True)
        labels = [label for label, _args in attempts]
        self.assertEqual(labels[0], "current yt-dlp defaults")
        self.assertFalse(any("Live YouTube session" in label for label in labels))
        self.assertFalse(any("--cookies" in args for _label, args in attempts))

    def test_saved_youtube_session_lives_outside_project_tree(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as root_tmp:
            with patch.dict("os.environ", {"LOCALAPPDATA": tmp, "XDG_STATE_HOME": tmp}):
                path = saved_session_path(Path(root_tmp))
            self.assertEqual(path.name, "youtube_session.txt")
            self.assertIn("PianoAutoPlayer", path.parts)
            self.assertNotIn(str(Path(root_tmp).resolve()), str(path.resolve()))
        self.assertIn("data/youtube_session.txt", Path(".gitignore").read_text(encoding="utf-8"))

    def test_legacy_session_is_removed_when_external_session_exists(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as root_tmp:
            root = Path(root_tmp)
            legacy = root / "data" / "youtube_session.txt"
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text("LOGIN_INFO=legacy; SID=legacy_sid", encoding="utf-8")
            with patch.dict("os.environ", {"LOCALAPPDATA": tmp, "XDG_STATE_HOME": tmp}):
                external = saved_session_path(root)
                external.write_text("LOGIN_INFO=current; SID=current_sid", encoding="utf-8")
                netscape, summary = load_saved_session(root)
            self.assertTrue(summary["has_account_cookies"])
            self.assertIn("current_sid", netscape)
            self.assertFalse(legacy.exists())

    def test_browser_does_not_persist_raw_session_in_local_storage(self):
        js = Path("web/youtube_piano.js").read_text(encoding="utf-8")
        self.assertNotIn('localStorage.setItem("piano_youtube_session"', js)
        self.assertIn('localStorage.removeItem("piano_youtube_session")', js)

    def test_new_modules_respect_line_cap(self):
        for name in ["app/audio_consensus.py", "app/basic_pitch_consensus.py", "app/audio_engine.py"]:
            self.assertLessEqual(len(Path(name).read_text(encoding="utf-8").splitlines()), 450, name)


if __name__ == "__main__":
    unittest.main()
