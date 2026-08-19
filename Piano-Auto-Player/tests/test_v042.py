import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.audio_transcriber import YouTubePianoTranscriber


class V042YouTubeChallengeTests(unittest.TestCase):
    def test_dependency_readiness_requires_js_runtime(self):
        with tempfile.TemporaryDirectory() as temp_name:
            worker = YouTubePianoTranscriber(Path(temp_name))
            with patch.object(worker, "_venv_python", return_value="python"), \
                 patch.object(worker, "_basic_pitch_exe", return_value="basic-pitch"), \
                 patch("app.audio_transcriber.shutil.which") as which:
                which.side_effect = lambda name: "C:/ffmpeg.exe" if name in {"ffmpeg", "ffprobe"} else None
                deps = worker.dependencies()
            self.assertFalse(deps["ready"])
            self.assertFalse(deps["js_runtime"])

    def test_challenge_args_enable_ejs_and_detected_runtime(self):
        worker = YouTubePianoTranscriber(Path("."))
        with patch.object(worker, "_js_runtime", return_value=("deno", "C:/Tools/deno.exe", "2.4.0")):
            args = worker._challenge_args()
        self.assertIn("--js-runtimes", args)
        self.assertIn("deno:C:/Tools/deno.exe", args)

    def test_current_attempts_include_modern_clients_and_browser_defaults(self):
        attempts = YouTubePianoTranscriber._youtube_attempts("auto")
        rows = dict(attempts)
        self.assertIn("current yt-dlp defaults", rows)
        self.assertIn("embedded fallback", rows)
        self.assertIn("Safari HLS fallback", rows)
        self.assertIn("mweb + PO token provider", rows)
        self.assertIn("web_embedded", rows["embedded fallback"][-1])
        self.assertNotIn("Chrome session defaults", rows)
        chrome_rows = dict(YouTubePianoTranscriber._youtube_attempts("chrome"))
        self.assertEqual(chrome_rows["Chrome session defaults"][:2], ["--cookies-from-browser", "chrome"])

    def test_download_command_always_carries_challenge_solver(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            worker = YouTubePianoTranscriber(root)
            temp = root / "temp"; temp.mkdir()
            seen = []

            def fake_run(command, timeout):
                seen.append(command)
                template = Path(command[command.index("-o") + 1])
                Path(str(template).replace("%(ext)s", "wav")).write_bytes(b"RIFF")
                return subprocess.CompletedProcess(command, 0, "Spider Man Song Original [Remastered]\n", "")

            with patch.object(worker, "_challenge_args", return_value=["--js-runtimes", "deno:C:/deno.exe"]), \
                 patch.object(worker, "_run_process", side_effect=fake_run):
                title, audio, method = worker._download_audio("job", "python", "https://youtube.com/watch?v=x", temp, "anonymous")
            self.assertEqual(title, "Spider Man Song Original [Remastered]")
            self.assertTrue(audio.exists())
            self.assertEqual(method, "current yt-dlp defaults")
            self.assertIn("deno:C:/deno.exe", seen[0])

    def test_setup_installs_modern_ytdlp_stack_and_deno(self):
        setup = Path("setup-youtube-piano.bat").read_text(encoding="utf-8")
        self.assertIn('"yt-dlp[default]"', setup)
        self.assertIn("DenoLand.Deno", setup)

    def test_ui_reports_js_runtime_dependency(self):
        js = Path("web/youtube_piano.js").read_text(encoding="utf-8")
        self.assertIn("deps.js_runtime", js)
        self.assertIn("challenge solver", js)

    def test_v042_sources_stay_modular(self):
        for name in ["app/audio_transcriber.py", "web/youtube_piano.js", "setup-youtube-piano.bat"]:
            self.assertLessEqual(len(Path(name).read_text(encoding="utf-8").splitlines()), 450, name)


if __name__ == "__main__":
    unittest.main()
