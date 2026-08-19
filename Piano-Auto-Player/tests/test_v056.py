import unittest
from pathlib import Path


class V056LiveSourceRoutingTests(unittest.TestCase):
    def test_media_ui_defaults_to_live_source_not_reference_substitution(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        self.assertIn('value="live">Live source — exact pasted audio/video', html)
        self.assertIn('value="fallback">Live source + alternate recording fallback', html)
        self.assertIn("never swaps in a retained sheet or MIDI", html)
        self.assertIn('id="youtubeRetryActions"', html)

    def test_media_controller_never_auto_imports_sheet_or_midi(self):
        js = Path("web/youtube_piano.js").read_text(encoding="utf-8")
        self.assertNotIn("useBestReference", js)
        self.assertNotIn("api.bestReference(", js)
        self.assertNotIn("api.importSheet(", js)
        self.assertIn("api.startYoutube(value", js)
        self.assertIn("Loaded from the submitted source", js)

    def test_exact_youtube_is_default_and_alternate_fallback_is_opt_in(self):
        js = Path("web/youtube_piano.js").read_text(encoding="utf-8")
        self.assertIn('const routeMode = route?.value || "live"', js)
        self.assertIn('routeMode === "fallback"', js)
        self.assertIn("excludeUrl: value", js)

    def test_bot_challenge_offers_explicit_exact_source_browser_retries(self):
        js = Path("web/youtube_piano.js").read_text(encoding="utf-8")
        self.assertIn("showAuthRetries(value", js)
        self.assertIn("Retry this exact YouTube video", js)
        self.assertIn("accessOverride: browser", js)
        self.assertIn('for (const browser of ["chrome", "edge", "firefox"])', js)

    def test_spotify_routes_to_public_recording_transcription_not_sheet_lookup(self):
        js = Path("web/youtube_piano.js").read_text(encoding="utf-8")
        self.assertIn("finding a public recording to transcribe live", js)
        self.assertIn("No sheet or MIDI was substituted", js)
        self.assertNotIn("bestReference(", js)

    def test_version_and_line_cap(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        server = Path("app/server.py").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v0.6.21", html)
        self.assertIn("Piano Auto Player v0.6.21 running", server)
        for name in [
            "app/audio_transcriber.py",
            "app/media_reference.py",
            "app/source_discovery.py",
            "app/server.py",
            "web/youtube_piano.js",
            "web/app.js",
        ]:
            lines = len(Path(name).read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(lines, 450, f"{name} exceeded 450 lines ({lines})")


if __name__ == "__main__":
    unittest.main()
