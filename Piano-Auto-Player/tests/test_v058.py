import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.audio_transcriber import YouTubePianoTranscriber
from app.youtube_access import parse_session_cookies, profile_inventory, youtube_attempts


class V058YouTubeSessionBridgeTests(unittest.TestCase):
    def test_parse_session_cookies_header_format(self):
        sample = 'LOGIN_INFO=AFmmF2swRQI; __Secure-3PSID=g.a000test; PREF=f4=4000000; VISITOR_INFO1_LIVE=xyz'
        netscape, summary = parse_session_cookies(sample)
        self.assertEqual(summary['total_cookies'], 4)
        self.assertTrue(summary['has_account_cookies'])
        self.assertIn('LOGIN_INFO', summary['account_cookie_names'])
        self.assertIn('__Secure-3PSID', summary['account_cookie_names'])
        self.assertIn('# Netscape HTTP Cookie File', netscape)
        self.assertIn('.youtube.com\tTRUE\t/\tTRUE', netscape)

    def test_parse_session_cookies_netscape_format(self):
        sample = (
            '# Netscape HTTP Cookie File\n'
            '.youtube.com\tTRUE\t/\tTRUE\t1800000000\tLOGIN_INFO\tAFmmF2\n'
            '.youtube.com\tTRUE\t/\tTRUE\t1800000000\tSID\tsidval123\n'
        )
        netscape, summary = parse_session_cookies(sample)
        self.assertEqual(summary['total_cookies'], 2)
        self.assertTrue(summary['has_account_cookies'])
        self.assertIn('SID', summary['account_cookie_names'])

    def test_session_attempts_use_explicit_cookie_file(self):
        with tempfile.NamedTemporaryFile('w', delete=False) as f:
            f.write('# Netscape HTTP Cookie File')
            cookie_path = f.name
        try:
            attempts = youtube_attempts('session', cookie_path)
            labels = [l for l, _a in attempts]
            self.assertIn('Live YouTube session Safari-HLS', labels)
            self.assertIn('Live YouTube session defaults', labels)
            self.assertIn('Live YouTube session Safari-HLS + PO', labels)
            all_args = [arg for _label, args in attempts for arg in args]
            self.assertIn('--cookies', all_args)
            self.assertIn(cookie_path, all_args)
        finally:
            Path(cookie_path).unlink(missing_ok=True)

    def test_profile_inventory_reports_browser_keys(self):
        inv = profile_inventory()
        self.assertIn('chrome', inv)
        self.assertIn('edge', inv)
        self.assertIn('firefox', inv)
        self.assertIsInstance(inv['chrome'], list)

    def test_transcriber_diagnostics_and_session_staging(self):
        worker = YouTubePianoTranscriber(Path('.'))
        summary = worker.set_session_cookies('LOGIN_INFO=secret; SID=sidvalue', persist=False)
        self.assertTrue(summary['has_account_cookies'])
        status = worker.session_status()
        self.assertEqual(status['total_cookies'], 2)
        with patch.object(worker, 'dependencies', return_value={'ready': False}):
            diag = worker.diagnostics('https://www.youtube.com/watch?v=BUD33xXIFt4')
        self.assertIn('dependencies', diag)
        self.assertIn('profiles', diag)
        self.assertIn('session', diag)
        self.assertTrue(diag['session']['has_account_cookies'])

    def test_modular_source_line_limits(self):
        for name in [
            'app/audio_transcriber.py',
            'app/youtube_access.py',
            'app/server.py',
            'web/youtube_piano.js',
            'web/app.js',
        ]:
            lines = len(Path(name).read_text(encoding='utf-8').splitlines())
            self.assertLessEqual(lines, 450, f'{name} has {lines} lines (limit 450)')


if __name__ == '__main__':
    unittest.main()
