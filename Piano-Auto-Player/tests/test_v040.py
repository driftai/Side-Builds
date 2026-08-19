import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.audio_transcriber import YouTubePianoTranscriber
from app.notation_quality import sheet_contamination_reason
from app.providers.extractor import score_sheet_candidate
from app.providers.roblox_current import extract_button_notation, find_midi_download
from app.providers.robloxpianosheet import RobloxPianoSheetProvider
from app.providers.toonkeys import ToonKeysProvider
from app.providers.vpsheet import VPSheetProvider
from app.providers.registry import ProviderRegistry
from app.sheet_validation import validate_sheet_text


PRIVACY_PAYLOAD = r'''application available for download on the Apple App Store and Google Play Store. Account means a unique account created by You to access our Service or parts of our Service. Company referred to as either the Company, We, Us or Our in this Agreement refers to website. Cookies are files that are placed on Your computer, mobile device, or any other device by a website, containing the details of Your browsing history. Personal Data is any information that relates to an identified or identifiable individual. Service refers to the products, features, or tools powered by artificial intelligence. 3:[\"$\",\"$L19\",null,{\"formats\":\"$undefined\",\"locale\":\"en\",\"messages\":{\"metadata\":{\"title\":\"Roblox Piano Sheets | Free Virtual Piano & MIDI Converter\",\"description\":\"Discover 1000+ free Roblox piano sheets\"}}}]'''


def _vlq(value: int) -> bytes:
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append(0x80 | (value & 0x7F)); value >>= 7
    return bytes(reversed(out))


def _midi() -> bytes:
    track = bytearray(b"\x00\xff\x51\x03\x07\xa1\x20\x00\x90\x3c\x50\x00\x90\x40\x50")
    track += _vlq(480) + b"\x80\x3c\x00\x00\x80\x40\x00\x00\xff\x2f\x00"
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, 480) + b"MTrk" + struct.pack(">I", len(track)) + bytes(track)


class V040HostSafetyTests(unittest.TestCase):
    def test_user_privacy_nextjs_payload_is_never_notation(self):
        self.assertTrue(sheet_contamination_reason(PRIVACY_PAYLOAD))
        self.assertLess(score_sheet_candidate(PRIVACY_PAYLOAD), 0)
        with self.assertRaisesRegex(ValueError, "non-piano data"):
            validate_sheet_text(PRIVACY_PAYLOAD)

    def test_real_grid_sheet_still_validates(self):
        sheet = "[4qgc] _ [sgH] [5wh] - [tj] [6yk] | [7ul] [8ip]"
        self.assertEqual(sheet_contamination_reason(sheet), "")
        validate_sheet_text(sheet)

    def test_current_roblox_button_extractor_ignores_page_prose(self):
        tokens = ["[4qgc]", "_", "s", "g", "H", "[5wh]", "-", "t", "j", "[6yk]", "|", "u"]
        page = f"<p>{PRIVACY_PAYLOAD}</p>" + "".join(f"<button>{token}</button>" for token in tokens)
        sheet = extract_button_notation(page, expected_tokens=len(tokens))
        self.assertEqual(sheet.split(), tokens)

    def test_roblox_provider_prefers_host_midi_over_page_scraping(self):
        page = '<h1>Pokemon Theme Roblox Piano Sheet</h1><div>935 playable tokens</div><a href="/download/pokemon.mid">Download MIDI</a>'
        self.assertEqual(find_midi_download(page, "https://robloxpianosheet.com/sheets/pokemon-theme"), "https://robloxpianosheet.com/download/pokemon.mid")
        with patch("app.providers.robloxpianosheet.get_html", return_value=(page, "https://robloxpianosheet.com/sheets/pokemon-theme")), \
             patch("app.providers.robloxpianosheet.get_bytes", return_value=(_midi(), "https://robloxpianosheet.com/download/pokemon.mid")):
            song = RobloxPianoSheetProvider().fetch("https://robloxpianosheet.com/sheets/pokemon-theme")
        self.assertEqual(song["timing_profile"], "midi")
        self.assertEqual(song["fidelity"], "midi")
        self.assertTrue(song["performance"])
        self.assertTrue(song["sheet"])

    def test_registry_blocks_privacy_prose_from_any_provider(self):
        class PollutedProvider:
            id = "polluted-prose"
            def accepts(self, _url): return True
            def fetch(self, _url): return {"title": "bad", "sheet": PRIVACY_PAYLOAD}
        registry = ProviderRegistry(); provider = PollutedProvider()
        registry.providers.insert(0, provider); registry.by_id[provider.id] = provider
        with self.assertRaisesRegex(ValueError, "non-piano data"):
            registry.fetch("https://example.invalid/bad", provider.id)

    def test_vpsheet_client_loading_page_fails_closed(self):
        page = '<html><body><h1>Avid - 86</h1><div>Loading sheet...</div><script>' + PRIVACY_PAYLOAD + '</script></body></html>'
        with patch("app.providers.vpsheet.get_html", return_value=(page, "https://vpsheet.com/sheet/avid-86")):
            with self.assertRaises(ValueError):
                VPSheetProvider().fetch("https://vpsheet.com/sheet/avid-86")

    def test_toonkeys_surfaces_exact_spider_man_catalog_row_without_faking_import(self):
        page = '''<table><tr><td>Spider Man Theme Song</td><td><a href="https://atlanticsheet.com/toon-012">Sheet</a></td><td><a href="https://patreon.com/post/1">MIDI</a></td><td><a href="https://youtube.com/watch?v=abc">YouTube</a></td></tr></table>'''
        provider = ToonKeysProvider()
        with patch("app.providers.toonkeys.get_html", return_value=(page, provider.BASE)):
            rows = provider.search("Spider-Man Theme Song")
        self.assertEqual(rows[0]["title"], "Spider Man Theme Song")
        self.assertFalse(rows[0]["importable"])
        self.assertEqual(rows[0]["video_url"], "https://youtube.com/watch?v=abc")


class V040YouTubePipelineTests(unittest.TestCase):
    def test_url_allowlist_accepts_supported_public_media_and_rejects_unknown_hosts(self):
        with self.assertRaisesRegex(ValueError, "supported"):
            YouTubePianoTranscriber._validated_url("https://example.com/watch?v=abc")
        self.assertEqual(YouTubePianoTranscriber._validated_url("https://audio.com/a/audio/song"), "https://audio.com/a/audio/song")
        self.assertEqual(YouTubePianoTranscriber._validated_url("https://www.youtube.com/watch?v=knL0aKGruUc"), "https://www.youtube.com/watch?v=knL0aKGruUc")

    def test_pipeline_turns_basic_pitch_midi_into_existing_timed_performance(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            scripts = root / ".youtube-piano-venv" / "Scripts"; scripts.mkdir(parents=True)
            (scripts / "python.exe").write_bytes(b"")
            (scripts / "basic-pitch.exe").write_bytes(b"")
            worker = YouTubePianoTranscriber(root)
            job_id = "job123"; url = "https://youtu.be/knL0aKGruUc"
            worker._jobs[job_id] = {"id": job_id, "status": "queued", "url": url}

            def fake_download(_job_id, _python, _url, temp, _access, _title_hint=""):
                audio = temp / "source.wav"
                audio.write_bytes(b"RIFFfake")
                return "Spider-Man Theme Song", audio, "standard YouTube"

            def fake_basic_pitch(command):
                outdir = Path(command[1]); (outdir / "transcribed.mid").write_bytes(_midi())

            with patch.object(worker, "_download_audio", side_effect=fake_download), \
                 patch.object(worker, "_run_checked", side_effect=fake_basic_pitch):
                worker._run(job_id, url, quality="rhythm_clean")
            state = worker.status(job_id)
            self.assertEqual(state["status"], "complete")
            self.assertEqual(state["result"]["timing_profile"], "youtube_basic_pitch")
            self.assertEqual(state["result"]["source"], "YouTube → Basic Pitch")
            self.assertTrue(state["result"]["performance"])
            self.assertTrue(state["result"]["sheet"])

    def test_ui_exposes_optional_youtube_transcriber_without_core_dependency(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        api = Path("web/api.js").read_text(encoding="utf-8")
        self.assertIn('id="youtubePianoForm"', html)
        self.assertIn("Transcribe to piano", html)
        self.assertIn("/api/youtube", api)
        self.assertTrue(Path("setup-youtube-piano.bat").exists())
        self.assertIn("No third-party", Path("requirements.txt").read_text(encoding="utf-8"))

    def test_v040_touched_sources_stay_modular(self):
        names = [
            "app/audio_transcriber.py", "app/notation_quality.py", "app/providers/roblox_current.py",
            "app/providers/robloxpianosheet.py", "app/providers/toonkeys.py", "app/providers/registry.py",
            "app/server.py", "web/app.js", "web/api.js", "web/youtube_piano.js", "web/styles.css", "web/index.html",
        ]
        for name in names:
            count = len(Path(name).read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(count, 450, f"{name} has {count} lines")


if __name__ == "__main__":
    unittest.main()
