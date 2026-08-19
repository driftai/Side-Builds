import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.audio_transcriber import YouTubePianoTranscriber


class V043YouTubeRuntimeTests(unittest.TestCase):
    def test_old_node_is_not_accepted(self):
        worker = YouTubePianoTranscriber(Path('.'))
        with patch('app.audio_transcriber.shutil.which') as which, patch.object(worker, '_runtime_version') as version:
            which.side_effect = lambda name: 'C:/node.exe' if name == 'node' else None
            version.return_value = (20, 18, 1)
            self.assertIsNone(worker._js_runtime())
            self.assertIn('needs 22.0.0+', worker._runtime_issue())

    def test_supported_node_is_accepted(self):
        worker = YouTubePianoTranscriber(Path('.'))
        with patch('app.audio_transcriber.shutil.which') as which, patch.object(worker, '_runtime_version') as version:
            which.side_effect = lambda name: 'C:/node.exe' if name == 'node' else None
            version.return_value = (22, 12, 0)
            self.assertEqual(worker._js_runtime(), ('node', 'C:/node.exe', '22.12.0'))

    def test_deno_is_preferred(self):
        worker = YouTubePianoTranscriber(Path('.'))
        with patch('app.audio_transcriber.shutil.which') as which, patch.object(worker, '_runtime_version') as version:
            which.side_effect = lambda name: {'deno': 'C:/deno.exe', 'node': 'C:/node.exe'}.get(name)
            version.return_value = (2, 4, 0)
            self.assertEqual(worker._js_runtime()[0], 'deno')

    def test_python_deprecation_warning_does_not_mask_youtube_error(self):
        cp = subprocess.CompletedProcess([], 1, '', 'Deprecated Feature: Support for Python version 3.10 has been deprecated. Please update to Python 3.11 or above\nERROR: [youtube] abc: Sign in to confirm you are not a bot')
        text = YouTubePianoTranscriber._error_text(cp)
        self.assertIn('Sign in to confirm', text)
        self.assertNotIn('deprecated', text.lower())

    def test_attempts_avoid_stale_android_vr_and_tv_downgraded(self):
        flat = repr(YouTubePianoTranscriber._youtube_attempts('auto'))
        self.assertIn('web_embedded', flat)
        self.assertIn('web_safari', flat)
        self.assertNotIn('android_vr', flat)
        self.assertNotIn('tv_downgraded', flat)

    def test_challenge_uses_installed_ejs_without_remote_fetch(self):
        worker = YouTubePianoTranscriber(Path('.'))
        with patch.object(worker, '_js_runtime', return_value=('deno', 'C:/deno.exe', '2.4.0')):
            args = worker._challenge_args()
        self.assertEqual(args, ['--js-runtimes', 'deno:C:/deno.exe'])

    def test_setup_prefers_deno_and_validates_node_22(self):
        setup = Path('setup-youtube-piano.bat').read_text(encoding='utf-8')
        self.assertIn('DenoLand.Deno', setup)
        self.assertIn('LSS 22', setup)
        self.assertIn('--pre "yt-dlp[default]"', setup)
        self.assertNotIn(' yt-dlp-ejs basic-pitch', setup)

    def test_version_strings_are_current(self):
        self.assertRegex(Path('app/server.py').read_text(encoding='utf-8'), r'v0\.\d+\.\d+ running')
        self.assertRegex(Path('web/index.html').read_text(encoding='utf-8'), r'v0\.\d+\.\d+')

    def test_v043_sources_stay_modular(self):
        for name in ['app/audio_transcriber.py', 'web/youtube_piano.js', 'setup-youtube-piano.bat']:
            self.assertLessEqual(len(Path(name).read_text(encoding='utf-8').splitlines()), 450, name)


if __name__ == '__main__':
    unittest.main()
