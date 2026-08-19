import unittest
from pathlib import Path
from unittest.mock import patch

from app.audio_stability_reducer import reduce_unstable_notes
from app.audio_sustain_repair import SustainRepairConfig, repair_sustain_fragments
from app.providers.extractor import extract_sheet_metadata
from app.providers.gamepianosheets import GamePianoSheetsProvider
from app.providers.registry import ProviderRegistry


class V053AdaptiveStabilityTests(unittest.TestCase):
    def test_overlapping_same_pitch_fragment_is_joined(self):
        notes = [(0.0, 520.0, 60, 52), (485.0, 830.0, 60, 56)]
        repaired, joins = repair_sustain_fragments(notes)
        self.assertEqual(joins, 1)
        self.assertEqual(repaired, [(0.0, 830.0, 60, 56)])

    def test_strong_overlapping_reattack_stays_separate(self):
        cfg = SustainRepairConfig(reattack_velocity_jump=12)
        notes = [(0.0, 520.0, 60, 44), (485.0, 830.0, 60, 68)]
        repaired, joins = repair_sustain_fragments(notes, cfg)
        self.assertEqual(joins, 0)
        self.assertEqual(repaired, notes)

    def test_stability_guard_only_activates_on_heavy_fragmentation(self):
        notes = [(0.0, 220.0, 60, 60), (0.0, 180.0, 64, 54), (0.0, 90.0, 91, 43)]
        stable, dropped, active = reduce_unstable_notes(notes, raw_count=1000, sustain_joins=40)
        self.assertFalse(active)
        self.assertEqual(dropped, 0)
        self.assertEqual(stable, notes)

    def test_stability_guard_prunes_unsupported_extra_voice(self):
        notes = [
            (0.0, 260.0, 60, 66), (0.0, 250.0, 64, 62), (0.0, 75.0, 91, 43),
            (120.0, 300.0, 62, 69), (240.0, 420.0, 64, 70),
        ]
        reduced, dropped, active = reduce_unstable_notes(notes, raw_count=1000, sustain_joins=300)
        self.assertTrue(active)
        self.assertGreaterEqual(dropped, 1)
        self.assertNotIn((0.0, 75.0, 91, 43), reduced)
        self.assertIn((0.0, 260.0, 60, 66), reduced)


class V053ReferenceProviderTests(unittest.TestCase):
    def test_about_minutes_metadata_is_understood(self):
        html = '<div>Loading piano...</div><div>311 notes</div><div>About 2.6 minutes</div>'
        metadata = extract_sheet_metadata(html)
        self.assertEqual(metadata['note_count'], 311)
        self.assertAlmostEqual(metadata['duration_seconds'], 156.0)

    @patch('app.providers.gamepianosheets.get_html')
    def test_game_piano_sheet_uses_sustain_aware_timing(self, mocked_html):
        notation = 'T [0 e]6---- O---- O--r[%0]-- O---- O--O----'
        page = f'<h1>in the pool - Roblox Piano Sheet</h1><div>About 2.6 minutes</div><pre>{notation}</pre>'
        mocked_html.return_value = (page, 'https://gamepianosheets.com/sheets/in-the-pool')
        song = GamePianoSheetsProvider().fetch('https://gamepianosheets.com/sheets/in-the-pool')
        self.assertEqual(song['timing_profile'], 'vpsheet')
        self.assertIn('[0 e]6', song['sheet'])
        self.assertGreater(song['recommended_interval_ms'], 0)

    def test_provider_is_in_default_registry(self):
        info = ProviderRegistry().info()
        self.assertIn('gamepianosheets', {row['id'] for row in info})

    def test_v053_ui_and_line_cap(self):
        html = Path('web/index.html').read_text(encoding='utf-8')
        js = Path('web/youtube_piano.js').read_text(encoding='utf-8')
        server = Path('app/server.py').read_text(encoding='utf-8')
        self.assertIn('Piano Auto Player v0.6.21', html)
        self.assertIn('stability guard removed', js)
        self.assertIn('Piano Auto Player v0.6.21 running', server)
        for name in [
            'app/audio_stability_reducer.py', 'app/audio_sustain_repair.py',
            'app/audio_note_cleanup.py', 'app/providers/gamepianosheets.py',
            'app/providers/extractor.py', 'app/providers/registry.py',
            'app/audio_transcriber.py', 'app/server.py', 'web/youtube_piano.js', 'web/app.js',
        ]:
            lines = len(Path(name).read_text(encoding='utf-8').splitlines())
            self.assertLessEqual(lines, 450, f'{name} exceeded 450 lines ({lines})')


if __name__ == '__main__':
    unittest.main()
