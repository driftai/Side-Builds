import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.audio_transcriber import YouTubePianoTranscriber
from app.youtube_access import browser_diagnostic, youtube_attempts


class V057YouTubeBrowserSessionTests(unittest.TestCase):
    def test_explicit_browser_mode_never_appends_anonymous_attempts(self):
        with patch("app.youtube_access.browser_cookie_specs", return_value=["chrome", "chrome:Profile 1"]):
            attempts = youtube_attempts("chrome")
        labels = [label for label, _args in attempts]
        flat = repr(attempts)
        self.assertTrue(labels)
        self.assertNotIn("current yt-dlp defaults", labels)
        self.assertNotIn("embedded fallback", labels)
        self.assertNotIn("mweb + PO token provider", labels)
        self.assertIn("--cookies-from-browser", flat)
        self.assertIn("chrome:Profile 1", flat)

    def test_browser_hls_route_is_combined_and_never_exposes_missing_pot_formats(self):
        with patch("app.youtube_access.browser_cookie_specs", return_value=["chrome"]):
            rows = dict(youtube_attempts("chrome"))
        hls = rows["Chrome Safari-HLS session"]
        self.assertIn("youtube:player_client=web_safari", hls)
        self.assertIn("best[protocol^=m3u8]/best", hls)
        self.assertNotIn("formats=missing_pot", repr(rows))
        forced = rows["Chrome Safari-HLS + PO session"]
        self.assertIn("fetch_pot=always", repr(forced))

    def test_auto_mode_stays_cookie_free(self):
        attempts = youtube_attempts("auto")
        self.assertNotIn("--cookies-from-browser", repr(attempts))
        self.assertIn("mweb;fetch_pot=always", repr(attempts))

    def test_browser_diagnostics_distinguish_account_lock_and_missing_login(self):
        self.assertIn("signed-in YouTube account cookies", browser_diagnostic("[debug] [youtube] Found YouTube account cookies", "chrome"))
        self.assertIn("locked", browser_diagnostic("ERROR: Could not copy Chrome cookie database", "chrome"))
        self.assertIn("did not detect signed-in YouTube", browser_diagnostic("Extracted 821 cookies from chrome", "chrome"))

    def test_download_error_reports_browser_attempt_not_anonymous_tail(self):
        with tempfile.TemporaryDirectory() as temp_name:
            worker = YouTubePianoTranscriber(Path(temp_name))
            temp = Path(temp_name) / "temp"; temp.mkdir()
            cp = subprocess.CompletedProcess([], 1, "", "Extracted 900 cookies from chrome\nERROR: [youtube] x: Sign in to confirm you’re not a bot")
            with patch.object(worker, "_challenge_args", return_value=["--js-runtimes", "deno:C:/deno.exe"]), \
                 patch.object(worker, "_youtube_attempts", return_value=[("Chrome Safari-HLS session", ["--cookies-from-browser", "chrome"])]), \
                 patch.object(worker, "_run_process", return_value=cp):
                with self.assertRaises(RuntimeError) as ctx:
                    worker._download_audio("job", "python", "https://youtube.com/watch?v=x", temp, "chrome")
            text = str(ctx.exception)
            self.assertIn("browser attempts themselves", text)
            self.assertIn("did not detect signed-in YouTube", text)
            self.assertNotIn("embedded fallback", text)

    def test_dependency_status_exposes_ytdlp_version(self):
        worker = YouTubePianoTranscriber(Path("."))
        with patch.object(worker, "_venv_python", return_value="python"), \
             patch.object(worker, "_basic_pitch_exe", return_value="basic-pitch"), \
             patch.object(worker, "_js_runtime", return_value=("deno", "deno.exe", "2.9.5")), \
             patch.object(worker, "_package_version", side_effect=lambda name: "2026.08.17" if name == "yt-dlp" else "1.1.2"), \
             patch("app.audio_transcriber.shutil.which", return_value="C:/ffmpeg.exe"):
            deps = worker.dependencies()
        self.assertEqual(deps["yt_dlp_version"], "2026.08.17")

    def test_version_and_modular_line_cap(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        server = Path("app/server.py").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v0.6.21", html)
        self.assertIn("PianoAutoPlayer/0.6.21", server)
        for name in [
            "app/audio_transcriber.py", "app/youtube_access.py", "app/server.py",
            "web/youtube_piano.js", "web/app.js",
        ]:
            self.assertLessEqual(len(Path(name).read_text(encoding="utf-8").splitlines()), 450, name)


if __name__ == "__main__":
    unittest.main()
