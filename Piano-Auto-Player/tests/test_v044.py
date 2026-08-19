import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.audio_transcriber import YouTubePianoTranscriber
from app.source_discovery import AlternateSourceFinder, is_supported_media_url


class V044FallbackTests(unittest.TestCase):
    def test_auto_uses_po_provider_without_browser_cookie_databases(self):
        rows = dict(YouTubePianoTranscriber._youtube_attempts("auto"))
        self.assertIn("mweb + PO token provider", rows)
        flat = repr(rows)
        self.assertNotIn("--cookies-from-browser", flat)
        self.assertIn("player_client=mweb", repr(rows["mweb + PO token provider"]))

    def test_explicit_browser_mode_still_allows_cookies(self):
        rows = dict(YouTubePianoTranscriber._youtube_attempts("edge"))
        self.assertIn("Edge session defaults", rows)
        self.assertEqual(rows["Edge session defaults"][:2], ["--cookies-from-browser", "edge"])

    def test_public_media_allowlist(self):
        self.assertTrue(is_supported_media_url("https://audio.com/user/audio/song"))
        self.assertTrue(is_supported_media_url("https://artist.bandcamp.com/track/song"))
        self.assertFalse(is_supported_media_url("http://127.0.0.1/private.mp3"))
        worker = YouTubePianoTranscriber(Path("."))
        self.assertIn("audio.com", worker._validated_url("https://audio.com/user/audio/song"))
        with self.assertRaises(ValueError):
            worker._validated_url("https://example.com/song.mp3")

    def test_public_media_download_uses_generic_ytdlp(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            worker = YouTubePianoTranscriber(root)
            temp = root / "temp"; temp.mkdir()
            def fake_run(command, timeout):
                template = Path(command[command.index("-o") + 1])
                Path(str(template).replace("%(ext)s", "wav")).write_bytes(b"RIFF")
                return subprocess.CompletedProcess(command, 0, "Spider Man Song Original [Remastered]\n", "")
            with patch.object(worker, "_run_process", side_effect=fake_run):
                title, audio, method = worker._download_audio("job", "python", "https://audio.com/a/audio/b", temp, "auto", "Spider Man")
            self.assertEqual(title, "Spider Man")
            self.assertTrue(audio.exists())
            self.assertIn("audio.com", method)

    def test_alternate_source_search_filters_and_ranks_public_media(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            worker = AlternateSourceFinder(root)
            rows = [
                {"title": "Spider Man Song Original [Remastered]", "href": "https://audio.com/a/audio/spider-man", "body": "download mp3"},
                {"title": "Random", "href": "https://example.com/random", "body": "not media"},
                {"title": "Spider Man", "href": "https://soundcloud.com/a/spider", "body": "music"},
            ]
            cp = subprocess.CompletedProcess([], 0, json.dumps(rows), "")
            with patch.object(worker, "_venv_python", return_value="python"), patch.object(worker, "_has_ddgs", return_value=True), patch("app.source_discovery.subprocess.run", return_value=cp):
                found = worker.search("Spider Man Song Original Remastered")
            self.assertEqual(found[0]["host"], "Audio.com")
            self.assertTrue(all("example.com" not in row["url"] for row in found))

    def test_setup_installs_wpc_and_ddgs(self):
        setup = Path("setup-youtube-piano.bat").read_text(encoding="utf-8")
        self.assertIn("yt-dlp-getpot-wpc", setup)
        self.assertIn(" ddgs", setup)

    def test_ui_has_alternate_source_flow_and_forwards_title(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        js = Path("web/youtube_piano.js").read_text(encoding="utf-8")
        app = Path("web/app.js").read_text(encoding="utf-8")
        self.assertIn("alternateSourceQuery", html)
        self.assertIn("alternateSources", js)
        self.assertIn('youtubePiano.transcribe(result.video_url, result.title || "")', app)

    def test_v044_sources_stay_modular(self):
        for name in ["app/audio_transcriber.py", "app/source_discovery.py", "app/ddgs_helper.py", "web/youtube_piano.js", "web/app.js"]:
            self.assertLessEqual(len(Path(name).read_text(encoding="utf-8").splitlines()), 450, name)


if __name__ == "__main__":
    unittest.main()
