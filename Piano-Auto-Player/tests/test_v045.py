import subprocess
import unittest
from pathlib import Path

from app.audio_transcriber import YouTubePianoTranscriber
from app.source_discovery import AlternateSourceFinder


class V045AutomaticFallbackTests(unittest.TestCase):
    def test_diagnostic_reports_exit_when_no_explicit_error(self):
        cp = subprocess.CompletedProcess([], 2, "", "[youtube] [jsc:deno] Solving JS challenges using deno\n[debug] final detail")
        text = YouTubePianoTranscriber._error_text(cp)
        self.assertIn("exit 2", text)
        self.assertIn("Solving JS challenges", text)

    def test_diagnostic_reports_missing_wav_after_zero_exit(self):
        cp = subprocess.CompletedProcess([], 0, "Song title\n", "")
        text = YouTubePianoTranscriber._error_text(cp)
        self.assertIn("no WAV file was created", text)

    def test_po_provider_is_verified_from_verbose_output(self):
        cp = subprocess.CompletedProcess([], 1, "", "[debug] [youtube] [pot] PO Token Providers: wpc-1.1.2 (external)")
        self.assertEqual(YouTubePianoTranscriber._po_provider_text(cp), "WPC PO provider loaded")
        missing = subprocess.CompletedProcess([], 1, "", "[debug] no provider line")
        self.assertIn("not advertised", YouTubePianoTranscriber._po_provider_text(missing))

    def test_youtube_url_alternate_search_uses_video_id(self):
        queries = AlternateSourceFinder._queries("https://www.youtube.com/watch?v=knL0aKGruUc")
        self.assertTrue(all("knL0aKGruUc" in query for query in queries))
        self.assertFalse(any("youtube.com" in query for query in queries))

    def test_exact_and_strong_title_confidence(self):
        exact_score, exact = AlternateSourceFinder._score(
            "Spider Man Song Original Remastered",
            {"title": "Spider Man Song Original [Remastered]", "body": "download mp3"},
            "audio.com",
        )
        strong_score, strong = AlternateSourceFinder._score(
            "Spider Man Song Original Remastered",
            {"title": "Download Spider Man Song Original [Remastered]", "body": "listen mp3"},
            "audio.com",
        )
        self.assertEqual(exact, "exact")
        self.assertEqual(strong, "strong")
        self.assertGreaterEqual(exact_score, 10)
        self.assertGreaterEqual(strong_score, 9.5)

    def test_ui_auto_opens_and_uses_high_confidence_alternate(self):
        js = Path("web/youtube_piano.js").read_text(encoding="utf-8")
        self.assertIn("alternateDisclosure.open = true", js)
        self.assertIn("Exact source unavailable · searching alternate public recordings", js)
        self.assertIn('row.confidence === "exact"', js)
        self.assertIn("allowFallback: false", js)

    def test_version_strings_are_v045(self):
        self.assertRegex(Path("app/server.py").read_text(encoding="utf-8"), r"v0\.\d+\.\d+ running")
        self.assertRegex(Path("web/index.html").read_text(encoding="utf-8"), r"v0\.\d+\.\d+")

    def test_v045_sources_stay_modular(self):
        for name in ["app/audio_transcriber.py", "app/source_discovery.py", "web/youtube_piano.js", "web/app.js"]:
            self.assertLessEqual(len(Path(name).read_text(encoding="utf-8").splitlines()), 450, name)


if __name__ == "__main__":
    unittest.main()
