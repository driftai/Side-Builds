import unittest
from pathlib import Path

from app.performance_notation import performance_to_sheet
from app.providers.registry import ProviderRegistry


class _TimedProvider:
    id = "timed-test"
    name = "Timed Test"

    def accepts(self, _url):
        return True

    def fetch(self, url):
        return {
            "title": "Nocturne",
            "artist": "",
            "sheet": "",
            "performance": [
                {"key": "q", "at_ms": 0, "duration_ms": 120, "midi_notes": [60]},
                {"key": "wer", "at_ms": 240, "duration_ms": 180, "midi_notes": [64, 67, 71]},
                {"key": "T", "at_ms": 500, "duration_ms": 100, "midi_notes": [66]},
            ],
            "source": self.name,
            "source_url": url,
            "timing_profile": "midi",
        }


class V038TimedImportVisibilityTests(unittest.TestCase):
    def test_performance_transcript_is_readable_sheet_not_blank(self):
        events = [
            {"key": "q", "at_ms": 0, "duration_ms": 100},
            {"key": "wer", "at_ms": 100, "duration_ms": 100},
            {"key": "T", "at_ms": 200, "duration_ms": 100},
        ]
        self.assertEqual(performance_to_sheet(events), "q [wer] T")

    def test_registry_populates_sheet_for_any_timed_provider(self):
        registry = ProviderRegistry()
        provider = _TimedProvider()
        registry.providers = [provider]
        registry.by_id = {provider.id: provider}
        result = registry.fetch("https://example.test/nocturne", provider.id)
        self.assertEqual(result["sheet"], "q [wer] T")
        self.assertEqual(len(result["performance"]), 3)
        self.assertEqual(result["timing_profile"], "midi")

    def test_timed_playback_no_longer_depends_on_blank_textarea(self):
        js = Path("web/app.js").read_text(encoding="utf-8")
        self.assertIn("function isTimedPerformance() { return activePerformance.length > 0; }", js)
        self.assertNotIn("activePerformance.length > 0 && !els.sheet.value.trim()", js)

    def test_manual_sheet_edit_still_discards_timed_performance(self):
        js = Path("web/app.js").read_text(encoding="utf-8")
        self.assertIn('els.sheet.addEventListener("input", () => { activeSongId = null; activePerformance = [];', js)


if __name__ == "__main__":
    unittest.main()
