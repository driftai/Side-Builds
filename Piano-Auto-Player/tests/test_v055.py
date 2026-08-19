import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.audio_transcriber import YouTubePianoTranscriber
from app.media_reference import MediaReferenceResolver
from app.providers.registry import ProviderRegistry


class V055ReferenceRoutingTests(unittest.TestCase):
    def test_noisy_title_normalizes_to_canonical_in_the_pool(self):
        title = "In The Pool Best Part (Edit Version) Chainsawman OST"
        queries = MediaReferenceResolver.reference_queries(title)
        self.assertIn("In The Pool Best Part (Edit Version) Chainsawman OST", queries)
        self.assertIn("In The Pool Chainsawman", queries)
        self.assertIn("In The Pool", queries)


    def test_bracket_and_suffix_cleaning_on_diverse_titles(self):
        cases = [
            (
                "Rick Astley - Never Gonna Give You Up (Official Music Video)",
                "Rick Astley",
                ["Rick Astley - Never Gonna Give You Up", "Never Gonna Give You Up"],
            ),
            (
                "Giorno's Theme (Il Vento D'oro) [JoJo's Bizarre Adventure Part 5 OST]",
                "",
                ["Giorno's Theme", "Il Vento D'oro"],
            ),
            (
                "Interstellar Main Theme (Cornfield Chase) - Hans Zimmer [Official Soundtrack]",
                "Hans Zimmer",
                ["Cornfield Chase", "Interstellar Main Theme"],
            ),
            (
                "Spider Man Song Original [Remastered]",
                "",
                ["Spider Man Song Original", "Spider Man Song"],
            ),
        ]
        for raw_title, artist, expected_variants in cases:
            queries = MediaReferenceResolver.reference_queries(raw_title, artist)
            for exp in expected_variants:
                self.assertTrue(any(exp.lower() in q.lower() for q in queries), f"Expected {exp} in {raw_title}, got: {queries}")


    def test_exact_reference_match_selects_human_sheet_and_skips_audio(self):
        registry = ProviderRegistry()
        mock_results = {
            "results": [
                {
                    "title": "In The Pool",
                    "artist": "",
                    "url": "https://virtualpianosheet.test/sheets/in-the-pool",
                    "provider": "virtualpianosheet",
                    "provider_name": "VirtualPianoSheet",
                    "importable": True,
                    "fidelity": None,
                },
                {
                    "title": "in the pool",
                    "artist": "",
                    "url": "https://musicboxmaniacs.test/explore/melody/in-the-pool_123/",
                    "provider": "musicboxmaniacs",
                    "provider_name": "Music Box Maniacs MIDI",
                    "importable": True,
                    "fidelity": "midi",
                },
            ],
            "errors": {},
        }
        with patch.object(registry, "search", return_value=mock_results):
            result = registry.best_reference("In The Pool Best Part (Edit Version) Chainsawman OST")

        self.assertIsNotNone(result["reference"])
        self.assertEqual(result["reference"]["title"].lower(), "in the pool")
        self.assertEqual(result["reference"]["reference_confidence"], "exact")
        self.assertTrue(result["skipped_audio"])
        self.assertIn("In The Pool", result["queries"])

    def test_no_reference_returns_none_allowing_audio_fallback(self):
        registry = ProviderRegistry()
        mock_results = {"results": [], "errors": {}}
        with patch.object(registry, "search", return_value=mock_results):
            result = registry.best_reference("Obscure Song Title 12345xyz")
        self.assertIsNone(result["reference"])
        self.assertFalse(result["skipped_audio"])


    def test_anonymous_bot_rejection_suggests_explicit_browser_session(self):
        worker = YouTubePianoTranscriber(Path("."))
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            bot_err = subprocess.CompletedProcess(
                [], 1, "", "ERROR: [youtube] 123: Sign in to confirm you’re not a bot. Use --cookies-from-browser"
            )
            with patch.object(worker, "_run_process", return_value=bot_err), \
                 patch.object(worker, "_js_runtime", return_value=("deno", "deno.exe", "2.9.5")):
                with self.assertRaises(RuntimeError) as ctx:
                    worker._download_audio("job1", "python", "https://www.youtube.com/watch?v=123", temp, "auto")
                err_msg = str(ctx.exception)
                self.assertIn("bot verification challenge", err_msg)
                self.assertIn("Chrome session", err_msg)
                self.assertIn("Edge session", err_msg)
                self.assertIn("Firefox session", err_msg)


    def test_explicit_browser_mode_passes_cookies_option(self):
        worker = YouTubePianoTranscriber(Path("."))
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            captured_cmds = []

            def fake_run(cmd, timeout=1800):
                captured_cmds.append(list(cmd))
                wav = temp / "source.wav"
                wav.write_bytes(b'RIFFfake')
                return subprocess.CompletedProcess(cmd, 0, f"Title\n[wav]\n", "")

            with patch.object(worker, "_run_process", side_effect=fake_run), \
                 patch.object(worker, "_js_runtime", return_value=("deno", "deno.exe", "2.9.5")):
                worker._download_audio("job1", "python", "https://www.youtube.com/watch?v=123", temp, "chrome")

            self.assertTrue(captured_cmds)
            cmd = captured_cmds[0]
            self.assertIn("--cookies-from-browser", cmd)
            idx = cmd.index("--cookies-from-browser")
            self.assertEqual(cmd[idx + 1], "chrome")

    def test_all_modified_sources_stay_modular_under_450_lines(self):
        for name in [
            "app/media_reference.py",
            "app/providers/registry.py",
            "app/audio_transcriber.py",
            "app/source_discovery.py",
            "app/ddgs_helper.py",
            "app/server.py",
            "web/youtube_piano.js",
            "web/app.js",
        ]:
            lines = len(Path(name).read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(lines, 450, f"{name} exceeded 450 lines ({lines})")


if __name__ == "__main__":
    unittest.main()
