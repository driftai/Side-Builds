import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class V0621CollapsibleAiConversionTests(unittest.TestCase):
    def test_media_conversion_is_native_collapsible_disclosure(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('<details id="mediaConversionDisclosure" class="youtube-piano-card media-conversion-card">', html)
        self.assertIn('class="media-conversion-summary"', html)
        self.assertIn('class="media-conversion-body"', html)
        self.assertNotIn('<details id="mediaConversionDisclosure" class="youtube-piano-card media-conversion-card" open>', html)

    def test_ai_conversion_label_replaces_experimental_badge(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('>AI-Conversion</span>', html)
        self.assertIn('AI audio-to-piano conversion', html)
        self.assertNotIn('<span class="mini-badge">experimental</span>', html)

    def test_existing_conversion_controls_remain_inside_panel(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        start = html.index('id="mediaConversionDisclosure"')
        end = html.index('id="searchMessage"', start)
        panel = html[start:end]
        for control in (
            'id="youtubePianoForm"',
            'id="mediaRouteMode"',
            'id="youtubeAccessMode"',
            'id="youtubeEngineMode"',
            'id="youtubeQualityMode"',
            'id="hifiConfidenceDisclosure"',
            'id="runDiagnosticsBtn"',
            'id="openSessionModalBtn"',
            'id="alternateSourceBtn"',
            'id="youtubePianoMessage"',
        ):
            self.assertIn(control, panel)

    def test_disclosure_styling_and_version(self):
        css = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        server = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn('.media-conversion-summary::after', css)
        self.assertIn('.media-conversion-card[open] > .media-conversion-summary::after', css)
        self.assertIn('.ai-conversion-badge { text-transform: none; }', css)
        self.assertIn('Piano Auto Player v0.6.21', html)
        self.assertIn('PianoAutoPlayer/0.6.21', server)

    def test_source_line_cap(self):
        for path in [*Path(ROOT / "app").glob("*.py"), *Path(ROOT / "web").glob("*.js")]:
            self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 450, str(path))


if __name__ == "__main__":
    unittest.main()
