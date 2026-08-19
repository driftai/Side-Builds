import unittest
from pathlib import Path

from app.audio_stability_reducer import consensus_stability_config, reduce_unstable_notes
from app.audio_sustain_repair import repair_sustain_fragments, repair_sustain_fragments_detailed


class V060DensePassageTests(unittest.TestCase):
    def test_chord_aligned_same_pitch_reattack_is_not_stitched(self):
        notes = [
            (0.0, 400.0, 60, 50),
            (410.0, 660.0, 60, 52),
            (408.0, 650.0, 64, 57),
            (412.0, 640.0, 67, 55),
        ]
        repaired, joins, protected = repair_sustain_fragments_detailed(notes)
        c_notes = [note for note in repaired if note[2] == 60]
        self.assertEqual(len(c_notes), 2)
        self.assertEqual(joins, 0)
        self.assertEqual(protected, 1)

    def test_sparse_confidence_dropout_still_joins(self):
        notes = [(0.0, 400.0, 60, 50), (410.0, 660.0, 60, 52)]
        repaired, joins = repair_sustain_fragments(notes)
        self.assertEqual(repaired, [(0.0, 660.0, 60, 52)])
        self.assertEqual(joins, 1)

    def test_consensus_stability_profile_keeps_five_voice_piano_chord(self):
        chord = [
            (0.0, 330.0, 60, 67),
            (1.0, 325.0, 64, 66),
            (2.0, 320.0, 67, 65),
            (3.0, 315.0, 71, 64),
            (4.0, 310.0, 72, 63),
        ]
        strict, strict_drops, strict_active = reduce_unstable_notes(chord, 1000, 300)
        accurate, accurate_drops, accurate_active = reduce_unstable_notes(
            chord, 1000, 300, consensus_stability_config()
        )
        self.assertTrue(strict_active and accurate_active)
        self.assertEqual(len(strict), 4)
        self.assertEqual(strict_drops, 1)
        self.assertEqual(len(accurate), 5)
        self.assertEqual(accurate_drops, 0)

    def test_ui_reports_dense_reattack_protection_and_version(self):
        js = Path('web/youtube_piano.js').read_text(encoding='utf-8')
        html = Path('web/index.html').read_text(encoding='utf-8')
        server = Path('app/server.py').read_text(encoding='utf-8')
        self.assertIn('dense reattacks preserved', js)
        self.assertIn('Piano Auto Player v0.6.21', html)
        self.assertIn('PianoAutoPlayer/0.6.21', server)

    def test_source_line_cap(self):
        for name in [
            'app/audio_sustain_repair.py', 'app/audio_stability_reducer.py',
            'app/audio_note_cleanup.py', 'web/youtube_piano.js', 'web/app.js',
        ]:
            lines = len(Path(name).read_text(encoding='utf-8').splitlines())
            self.assertLessEqual(lines, 450, f'{name} exceeded 450 lines ({lines})')


if __name__ == '__main__':
    unittest.main()
