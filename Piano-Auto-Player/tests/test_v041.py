import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.audio_transcriber import YouTubePianoTranscriber


class V041YouTubeRetryTests(unittest.TestCase):
    def test_anonymous_mode_retries_current_youtube_clients_without_cookies(self):
        attempts = YouTubePianoTranscriber._youtube_attempts("anonymous")
        labels = [label for label, _args in attempts]
        flat = [arg for _label, args in attempts for arg in args]
        self.assertEqual(labels[:3], ["current yt-dlp defaults", "embedded fallback", "mweb + PO token provider"])
        self.assertNotIn("--cookies-from-browser", flat)
        self.assertIn("youtube:player_client=web_embedded,default", flat)
        self.assertIn("youtube:player_client=web_safari", flat)
        self.assertNotIn("formats=missing_pot", flat)

    def test_auto_mode_avoids_cookie_databases_and_explicit_browser_mode_keeps_them(self):
        attempts = YouTubePianoTranscriber._youtube_attempts("auto")
        labels = [label for label, _args in attempts]
        self.assertIn("mweb + PO token provider", labels)
        self.assertNotIn("Chrome session defaults", labels)
        chrome = dict(YouTubePianoTranscriber._youtube_attempts("chrome"))["Chrome Safari-HLS session"]
        self.assertEqual(chrome[chrome.index("--cookies-from-browser") + 1], "chrome")
        self.assertIn("youtube:player_client=web_safari", chrome)
        self.assertNotIn("formats=missing_pot", chrome)

    def test_download_retries_after_video_not_available_and_keeps_successful_method(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            worker = YouTubePianoTranscriber(root)
            temp = root / "temp"; temp.mkdir()
            calls = []

            def fake_run(command, timeout):
                calls.append(command)
                if len(calls) == 1:
                    return subprocess.CompletedProcess(command, 1, "", "ERROR: [youtube] x: This video is not available")
                template = Path(command[command.index("-o") + 1])
                Path(str(template).replace("%(ext)s", "wav")).write_bytes(b"RIFF")
                return subprocess.CompletedProcess(command, 0, "Spider-Man Theme Song\n", "")

            with patch.object(worker, "_challenge_args", return_value=["--remote-components", "ejs:github", "--js-runtimes", "deno:C:/deno.exe"]), patch.object(worker, "_run_process", side_effect=fake_run):
                title, audio, method = worker._download_audio("job", "python", "https://youtube.com/watch?v=x", temp, "anonymous")
            self.assertEqual(title, "Spider-Man Theme Song")
            self.assertTrue(audio.exists())
            self.assertEqual(method, "embedded fallback")
            self.assertEqual(len(calls), 2)

    def test_access_mode_validation_is_closed(self):
        self.assertEqual(YouTubePianoTranscriber._validated_access("Chrome"), "chrome")
        with self.assertRaisesRegex(ValueError, "access mode"):
            YouTubePianoTranscriber._validated_access("random-browser")


class V041CompactUITests(unittest.TestCase):
    def test_target_and_playback_help_are_collapsible(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        self.assertIn('class="control-disclosure target-window-disclosure"', html)
        self.assertIn('class="hint-card help-disclosure"', html)
        self.assertIn("Playback notes &amp; timing help", html)
        self.assertNotIn('<details class="hint-card help-disclosure" open', html)

    def test_youtube_access_mode_and_compact_select_css_exist(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        css = Path("web/styles.css").read_text(encoding="utf-8")
        api = Path("web/api.js").read_text(encoding="utf-8")
        self.assertIn('id="youtubeAccessMode"', html)
        self.assertIn("Automatic — retained session first, then anonymous fallbacks", html)
        self.assertIn(".compact-target select", css)
        self.assertIn("JSON.stringify({ url, access, title_hint: titleHint, quality, piano_layout: pianoLayout, engine })", api)

    def test_v041_sources_stay_modular(self):
        for name in ["app/audio_transcriber.py", "app/server.py", "web/api.js", "web/youtube_piano.js", "web/index.html", "web/styles.css"]:
            self.assertLessEqual(len(Path(name).read_text(encoding="utf-8").splitlines()), 450, name)


if __name__ == "__main__":
    unittest.main()
