import json
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from app.audio_transcriber import YouTubePianoTranscriber
from app.library import SongLibrary
from app.library_transfer import export_library_zip, export_song_bytes, import_library_bytes
from app.youtube_access import saved_session_path

ROOT = Path(__file__).resolve().parents[1]


class V0620RetentionAndLibraryTransferTests(unittest.TestCase):
    def _song(self, title="Test Song", song_id="song-test"):
        return {
            "id": song_id,
            "title": title,
            "kind": "performance",
            "performance": [{"at_ms": 0, "duration_ms": 120, "key": "a"}],
            "duration_ms": 120,
            "source": "youtube",
            "source_url": "https://example.invalid/watch?v=test",
            "timing_profile": "performance",
            "transcription_diagnostics": {"engine": "hifi_fusion", "score": 1},
        }

    def test_manual_youtube_session_is_persisted_and_reloaded(self):
        with tempfile.TemporaryDirectory() as state, tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            with patch.dict("os.environ", {"LOCALAPPDATA": state, "XDG_STATE_HOME": state}):
                first = YouTubePianoTranscriber(root)
                summary = first.set_session_cookies("LOGIN_INFO=fresh_login; SID=fresh_sid")
                self.assertTrue(summary["persisted"])
                self.assertTrue(saved_session_path(root).is_file())
                second = YouTubePianoTranscriber(root)
                status = second.session_status()
            self.assertGreaterEqual(status["total_cookies"], 2)
            self.assertTrue(status["persisted"])
            self.assertTrue(status["has_account_cookies"])

    def test_http_only_netscape_session_cookie_survives_retention_parse(self):
        from app.youtube_access import parse_session_cookies
        raw = "# Netscape HTTP Cookie File\n#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t1900000000\t__Secure-3PSID\tsecret"
        netscape, summary = parse_session_cookies(raw)
        self.assertEqual(summary["total_cookies"], 1)
        self.assertTrue(summary["has_account_cookies"])
        self.assertIn("__Secure-3PSID\tsecret", netscape)

    def test_devtools_expiry_is_retained_instead_of_forced_to_30_days(self):
        from app.youtube_access import parse_session_cookies
        netscape, summary = parse_session_cookies("SID\tfresh_sid\t.youtube.com\t/\t2027-09-21T22:07:16.607Z\t10\t✓\t✓")
        self.assertEqual(summary["total_cookies"], 1)
        expiry = int([line for line in netscape.splitlines() if line and not line.startswith("#")][0].split("\t")[4])
        self.assertGreater(expiry, 1800000000)

    def test_transcriber_reloads_disk_and_retains_ytdlp_cookie_refreshes(self):
        source = (ROOT / "app" / "audio_transcriber.py").read_text(encoding="utf-8")
        self.assertIn("disk_session, _ = load_saved_session(self.root)", source)
        self.assertIn('if "--cookies" in extra and session_file.is_file()', source)
        self.assertIn("self.set_session_cookies(session_file.read_text", source)

    def test_session_ui_unwraps_api_payload_and_describes_retention(self):
        js = (ROOT / "web" / "youtube_piano.js").read_text(encoding="utf-8")
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("payload?.session || payload", js)
        self.assertIn("cookies retained locally", js)
        self.assertIn("retained session first", html)
        self.assertNotIn('localStorage.setItem("piano_youtube_session"', js)

    def test_individual_song_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = SongLibrary(Path(tmp) / "source.json")
            saved = source.save(self._song())
            body, filename = export_song_bytes(saved)
            self.assertTrue(filename.endswith(".piano-song.json"))
            target = SongLibrary(Path(tmp) / "target.json")
            result = import_library_bytes(target, body, filename)
            self.assertEqual(result["imported"], 1)
            restored = target.get(saved["id"])
            self.assertEqual(restored["title"], "Test Song")
            self.assertEqual(restored["transcription_diagnostics"]["engine"], "hifi_fusion")

    def test_full_library_zip_round_trip_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = SongLibrary(Path(tmp) / "source.json")
            source.save(self._song("One", "song-one"))
            source.save(self._song("Two", "song-two"))
            body, filename, count = export_library_zip(source)
            self.assertEqual(count, 2)
            self.assertTrue(filename.endswith(".zip"))
            with zipfile.ZipFile(BytesIO(body)) as archive:
                manifest = json.loads(archive.read("manifest.json"))
                self.assertEqual(manifest["song_count"], 2)
                self.assertEqual(len([n for n in archive.namelist() if n.startswith("songs/")]), 2)
                self.assertFalse(any("youtube_session" in n for n in archive.namelist()))
            target = SongLibrary(Path(tmp) / "target.json")
            result = import_library_bytes(target, body, filename)
            self.assertEqual(result["imported"], 2)
            self.assertEqual(len(target.list()), 2)

    def test_reimport_same_song_replaces_by_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = SongLibrary(Path(tmp) / "songs.json")
            library.save(self._song("Old"))
            payload = {"format": "piano-auto-player-song", "schema": 1, "song": self._song("New")}
            result = import_library_bytes(library, json.dumps(payload).encode(), "song.piano-song.json")
            self.assertEqual(result["updated"], 1)
            self.assertEqual(library.get("song-test")["title"], "New")

    def test_library_ui_has_all_and_individual_transfer_controls(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        module = (ROOT / "web" / "library_transfer.js").read_text(encoding="utf-8")
        self.assertIn('id="exportLibraryBtn"', html)
        self.assertIn('id="importLibraryBtn"', html)
        self.assertIn('id="importLibraryInput"', html)
        self.assertIn('actionButton("Export"', app)
        self.assertIn("/api/library/export", module)
        self.assertIn("/api/library/import", module)

    def test_version_and_core_guard(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        server = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v0.6.21", html)
        self.assertIn("PianoAutoPlayer/0.6.21", server)
        for path in [*Path(ROOT / "app").glob("*.py"), *Path(ROOT / "web").glob("*.js")]:
            self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 450, str(path))


if __name__ == "__main__":
    unittest.main()
