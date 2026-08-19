import unittest
from unittest.mock import patch

from app.providers.extractor import count_sheet_notes, extract_sheet_from_html, score_sheet_candidate
from app.providers.onlinesequencer import OnlineSequencerProvider
from app.providers.registry import ProviderRegistry
from app.providers.vpsheet import VPSheetProvider
from app.sheet_validation import sheet_contamination_reason, validate_sheet_text


SVG_PATH = (
    "M20 3V17C20 19.2091 18.2091 21 16 21C13.7909 21 12 19.2091 12 17C12 14.7909 "
    "13.7909 13 16 13C16.7286 13 17.4117 13.1948 18 13.5351V5H9V17C9 19.2091 7.20914 21 5 "
    "21C2.79086 21 1 19.2091 1 17C1 14.7909 2.79086 13 5 13C5.72857 13 6.41165 13.1948 7 "
    "13.5351V3H20ZM5 19C6.10457 19 7 18.1046 7 17C7 15.8954 6.10457 15 5 15C3.89543 15 3 "
    "15.8954 3 17C3 18.1046 3.89543 19 5 19ZM16 19C17.1046 19 18 18.1046 18 17C18 15.8954 "
    "17.1046 15 16 15C14.8954 15 14 15.8954 14 17C14 18.1046 14.8954 19 16 19Z"
)


class V035ExtractionSafetyTests(unittest.TestCase):
    def test_exact_svg_payload_from_avid_is_rejected(self):
        self.assertEqual(count_sheet_notes(SVG_PATH), 368)
        self.assertIn("SVG", sheet_contamination_reason(SVG_PATH))
        self.assertLess(score_sheet_candidate(SVG_PATH), 0)
        with self.assertRaisesRegex(ValueError, "non-piano data"):
            validate_sheet_text(SVG_PATH)

    def test_real_vp_notation_still_passes(self):
        sheet = "[6u]uuu[3u]uuu [6u]-p-[3s]-- [%d]ddd[3d]sad [9z]lkz[8l]kjl"
        self.assertEqual(sheet_contamination_reason(sheet), "")
        validate_sheet_text(sheet)
        self.assertGreater(score_sheet_candidate(sheet), 0)

    def test_svg_cannot_win_when_host_note_count_matches_it(self):
        # This reproduces the nasty Avid failure mode: the SVG happens to contain
        # exactly 368 characters that the piano key map considers playable.
        real_sheet = "a-" * 367 + "a"
        self.assertEqual(count_sheet_notes(real_sheet), 368)
        page = (
            '<html><body><h1>Avid - 86</h1><div>368 notes 90.0s</div>'
            f'<script>const icon="{SVG_PATH}"; const sheetData="{real_sheet}";</script>'
            '</body></html>'
        )
        _title, _artist, extracted = extract_sheet_from_html(page, expected_notes=368)
        self.assertEqual(extracted, real_sheet)

    def test_page_with_only_svg_fails_instead_of_becoming_music(self):
        page = f'<html><body><h1>Bad extraction</h1><div>368 notes</div><script>const icon="{SVG_PATH}";</script></body></html>'
        with self.assertRaisesRegex(ValueError, "Could not find"):
            extract_sheet_from_html(page, expected_notes=368)

    def test_vpsheet_fetch_uses_real_candidate_after_svg_filter(self):
        real_sheet = "[6u]uuu[3u]uuu-" * 12
        page = (
            '<html><body><h1>Rush E</h1><div>120 BPM 120 notes 29.2s</div>'
            f'<script>const icon="{SVG_PATH}"; const sheetData="{real_sheet}";</script>'
            '</body></html>'
        )
        # Do not pin a fake note total here; this test is about provider extraction
        # and validation, while the exact-count collision is covered above.
        page = page.replace('120 notes ', '')
        with patch("app.providers.vpsheet.get_html", return_value=(page, "https://vpsheet.com/sheet/rush-e")):
            song = VPSheetProvider().fetch("https://vpsheet.com/sheet/rush-e")
        self.assertEqual(song["sheet"], real_sheet)
        self.assertEqual(song["timing_profile"], "vpsheet")


    def test_avid_catalog_fallback_survives_search_page_failure(self):
        with patch("app.providers.onlinesequencer.get_html", side_effect=OSError("offline")):
            rows = OnlineSequencerProvider().search("Avid 86 Hiroyuki Sawano")
        self.assertEqual(rows[0]["url"], "https://onlinesequencer.net/4619865")
        self.assertEqual(rows[0]["fidelity"], "midi")

    def test_avid_catalog_fallback_does_not_pollute_david_searches(self):
        self.assertEqual(OnlineSequencerProvider()._known_search_rows("David Bowie"), [])

    def test_registry_rejects_polluted_provider_output(self):
        class PollutedProvider:
            id = "polluted"
            def accepts(self, _url): return True
            def fetch(self, _url): return {"title": "bad", "sheet": SVG_PATH}

        registry = ProviderRegistry()
        provider = PollutedProvider()
        registry.providers.insert(0, provider)
        registry.by_id[provider.id] = provider
        with self.assertRaisesRegex(ValueError, "non-piano data"):
            registry.fetch("https://example.invalid/bad", provider.id)


if __name__ == "__main__":
    unittest.main()
