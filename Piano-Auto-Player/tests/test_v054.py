import unittest
from pathlib import Path
from unittest.mock import patch

from app.media_reference import MediaReferenceResolver
from app.providers.registry import ProviderRegistry
from app.source_discovery import AlternateSourceFinder, is_supported_media_url


class V054MediaResolverTests(unittest.TestCase):
    @patch.object(MediaReferenceResolver, '_fetch_json')
    def test_spotify_is_metadata_reference_not_direct_audio(self, fetch_json):
        fetch_json.return_value = {'title': 'in the pool'}
        result = MediaReferenceResolver().resolve('https://open.spotify.com/track/abc123')
        self.assertEqual(result['kind'], 'spotify')
        self.assertEqual(result['query'], 'in the pool')
        self.assertFalse(result['direct_audio'])
        self.assertIn('open.spotify.com/oembed', fetch_json.call_args.args[0])

    @patch.object(MediaReferenceResolver, '_fetch_json')
    def test_youtube_metadata_survives_downloader_block(self, fetch_json):
        fetch_json.return_value = {'title': 'in the pool', 'author_name': 'Kensuke Ushio'}
        result = MediaReferenceResolver().resolve('https://www.youtube.com/watch?v=blocked')
        self.assertEqual(result['kind'], 'youtube')
        self.assertEqual(result['query'], 'in the pool')
        self.assertEqual(result['artist'], 'Kensuke Ushio')
        self.assertTrue(result['direct_audio'])

    def test_reference_confidence_accepts_compact_title_extension(self):
        row = {'title': 'in the pool - Chainsaw Man the Movie', 'artist': 'kensuke ushio', 'importable': True}
        confidence, score = MediaReferenceResolver.reference_confidence('in the pool', row, 2312)
        self.assertEqual(confidence, 'exact')
        self.assertTrue(MediaReferenceResolver.acceptable_reference(confidence, score, row))


class V054ReferenceRoutingTests(unittest.TestCase):
    def test_registry_prefers_exact_importable_reference(self):
        registry = ProviderRegistry()
        rows = {
            'results': [
                {'title': 'in the pool - Chainsaw Man the Movie', 'artist': 'kensuke ushio', 'url': 'https://gamepianosheets.com/sheets/in-the-pool', 'provider': 'gamepianosheets', 'provider_name': 'Game Piano Sheets', 'importable': True},
                {'title': 'Pool Party', 'artist': '', 'url': 'https://example.test/pool', 'provider': 'fake', 'provider_name': 'Fake', 'importable': True},
            ],
            'errors': {},
        }
        with patch.object(registry, 'search', return_value=rows):
            result = registry.best_reference('in the pool')
        self.assertIsNotNone(result['reference'])
        self.assertEqual(result['reference']['provider'], 'gamepianosheets')
        self.assertEqual(result['reference']['reference_confidence'], 'exact')

    def test_unrelated_candidate_is_not_auto_selected(self):
        registry = ProviderRegistry()
        rows = {'results': [{'title': 'Swimming Lessons', 'artist': '', 'url': 'https://example.test/x', 'provider': 'fake', 'provider_name': 'Fake', 'importable': True}], 'errors': {}}
        with patch.object(registry, 'search', return_value=rows):
            result = registry.best_reference('in the pool')
        self.assertIsNone(result['reference'])

    def test_youtube_is_eligible_as_alternate_public_copy(self):
        self.assertTrue(is_supported_media_url('https://www.youtube.com/watch?v=abc'))
        queries = AlternateSourceFinder._queries('in the pool Kensuke Ushio')
        self.assertTrue(any('YouTube' in query for query in queries))


class V054SurfaceTests(unittest.TestCase):
    def test_v054_ui_and_line_cap(self):
        html = Path('web/index.html').read_text(encoding='utf-8')
        js = Path('web/youtube_piano.js').read_text(encoding='utf-8')
        server = Path('app/server.py').read_text(encoding='utf-8')
        self.assertIn('Media / Spotify', html)
        self.assertIn('id="mediaRouteMode"', html)
        self.assertIn('Live source', html)
        self.assertIn('Piano Auto Player v0.6.21', html)
        self.assertIn('startYoutube', js)
        self.assertIn('Piano Auto Player v0.6.21 running', server)
        for name in [
            'app/media_reference.py', 'app/source_discovery.py', 'app/providers/registry.py',
            'app/audio_transcriber.py', 'app/server.py', 'web/youtube_piano.js', 'web/app.js',
        ]:
            lines = len(Path(name).read_text(encoding='utf-8').splitlines())
            self.assertLessEqual(lines, 450, f'{name} exceeded 450 lines ({lines})')


if __name__ == '__main__':
    unittest.main()
