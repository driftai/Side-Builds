import csv
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.audio_note_cleanup import basic_pitch_args, performance_from_note_events, preset_for
from app.audio_transcriber import DownloadedAudio, YouTubePianoTranscriber
from app.playback import PlaybackController, PlaybackOptions


class V046MediaPipelineTests(unittest.TestCase):
    def test_ytdlp_command_includes_no_simulate_and_after_move_filepath(self):
        worker = YouTubePianoTranscriber(Path('.'))
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            captured = []

            def fake_run(command, timeout=1800):
                captured.append(list(command))
                wav = temp / 'custom_spider_track.wav'
                wav.write_bytes(b'RIFFfake')
                return subprocess.CompletedProcess(command, 0, f'Spider-Man Song\n{wav}\n', '')

            with patch.object(worker, '_run_process', side_effect=fake_run), \
                 patch.object(worker, '_js_runtime', return_value=('deno', 'deno.exe', '2.9.5')):
                artifact = worker._download_audio('job1', 'python', 'https://www.youtube.com/watch?v=knL0aKGruUc', temp, 'auto')

            cmd = captured[0]
            self.assertIn('--no-simulate', cmd)
            self.assertIn('after_move:%(filepath)s', cmd)
            self.assertEqual(artifact.path.name, 'custom_spider_track.wav')

    def test_discovery_handles_non_hardcoded_filename_and_non_wav_canonicalization(self):
        worker = YouTubePianoTranscriber(Path('.'))
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            opus_file = temp / 'arbitrary_name.opus'
            opus_file.write_bytes(b'OggSfake')

            def fake_run_checked(cmd):
                Path(cmd[-1]).write_bytes(b'RIFFconverted')

            with patch('app.audio_transcriber.shutil.which', return_value='C:\\ffmpeg\\bin\\ffmpeg.exe'), \
                 patch.object(worker, '_run_checked', side_effect=fake_run_checked):
                artifact = worker._discover_audio_artifact(
                    temp, subprocess.CompletedProcess([], 0, f'Custom Title\n{opus_file}\n', ''),
                    'https://audio.com/track', 'public source'
                )
            self.assertEqual(artifact.path.suffix, '.wav')
            self.assertEqual(artifact.audio_format, 'wav')

    def test_run_process_sets_utf8_environment_for_basic_pitch(self):
        worker = YouTubePianoTranscriber(Path('.'))
        with patch('app.audio_transcriber.subprocess.run') as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0, '', '')
            worker._run_process(['cmd'], timeout=10)
            env = mock_run.call_args[1].get('env', {})
            self.assertEqual(env.get('PYTHONIOENCODING'), 'utf-8')
            self.assertEqual(env.get('PYTHONUTF8'), '1')

    def test_downloaded_audio_keeps_tuple_unpacking_compatibility(self):
        artifact = DownloadedAudio('https://example.com/audio', 'Test', Path('test.wav'), 'wav', 'method', 12.0)
        title, path, method = artifact
        self.assertEqual((title, path, method), ('Test', Path('test.wav'), 'method'))

    def test_piano_clean_tunes_basic_pitch_and_disables_melodia(self):
        args = basic_pitch_args(preset_for('piano_clean'))
        self.assertIn('--save-note-events', args)
        self.assertIn('--no-melodia', args)
        self.assertIn('--onset-threshold', args)
        self.assertIn('--frame-threshold', args)
        self.assertNotIn('--no-melodia', basic_pitch_args(preset_for('balanced')))

    def test_note_event_cleanup_filters_noise_clusters_chords_and_bridges_sustain(self):
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / 'source_basic_pitch.csv'
            with path.open('w', newline='', encoding='utf-8') as handle:
                writer = csv.writer(handle)
                writer.writerow(['start_time_s', 'end_time_s', 'pitch_midi', 'velocity', 'pitch_bend'])
                writer.writerow([0.100, 0.220, 60, 96, ''])
                writer.writerow([0.118, 0.210, 64, 82, ''])
                writer.writerow([0.123, 0.205, 67, 12, ''])  # weak false positive
                writer.writerow([0.500, 0.610, 72, 100, ''])
            performance, stats = performance_from_note_events(path, preset_for('piano_clean'))
        self.assertEqual(len(performance), 2)
        self.assertEqual(performance[0]['midi_notes'], [60, 64])
        self.assertGreaterEqual(performance[0]['duration_ms'], 250)
        self.assertEqual(stats['raw_transcribed_notes'], 4)
        self.assertEqual(stats['note_count'], 3)
        self.assertEqual(stats['chord_count'], 1)

    def test_timed_external_hold_cannot_block_past_next_onset(self):
        events = [
            {'at_ms': 0.0, 'duration_ms': 420.0, 'key': 'a', 'midi_notes': [60]},
            {'at_ms': 120.0, 'duration_ms': 150.0, 'key': 's', 'midi_notes': [62]},
        ]
        options = PlaybackOptions(gate_percent=58, modifier_lead_ms=6, chord_spread_ms=4, timing_profile='youtube_basic_pitch')
        hold = PlaybackController._performance_hold_ms(events, 0, options, 1.0)
        self.assertLess(hold, 120.0)
        self.assertAlmostEqual(hold, 59.6, places=1)

    def test_quality_selector_and_payload_are_wired(self):
        html = Path('web/index.html').read_text(encoding='utf-8')
        api = Path('web/api.js').read_text(encoding='utf-8')
        js = Path('web/youtube_piano.js').read_text(encoding='utf-8')
        self.assertIn('id="youtubeQualityMode"', html)
        self.assertIn('Piano clean — cleaner solo piano', html)
        self.assertIn('title_hint: titleHint, quality', api)
        self.assertIn('quality?.value || "rhythm_accurate"', js)

    def test_v046_version_and_modularity(self):
        self.assertRegex(Path('app/server.py').read_text(encoding='utf-8'), r'v0\.\d+\.\d+ running')
        self.assertRegex(Path('web/index.html').read_text(encoding='utf-8'), r'v0\.\d+\.\d+')
        for name in [
            'app/audio_transcriber.py', 'app/audio_note_cleanup.py', 'app/source_discovery.py',
            'app/server.py', 'app/playback.py', 'web/youtube_piano.js', 'web/app.js',
        ]:
            lines = len(Path(name).read_text(encoding='utf-8').splitlines())
            self.assertLessEqual(lines, 450, f'{name} exceeded 450 lines ({lines})')


if __name__ == '__main__':
    unittest.main()
