import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class V064HifiInstallerTests(unittest.TestCase):
    def test_installer_avoids_windows_ncls_build(self):
        bat = (ROOT / "setup-hifi-piano.bat").read_text(encoding="utf-8")
        self.assertIn('pip install --upgrade --no-deps "transkun==2.0.1"', bat)
        self.assertIn('pretty-midi mir-eval pydub soxr moduleconf', bat)
        self.assertNotIn('pip install --upgrade "transkun==2.0.1"', bat)
        self.assertIn('https://download.pytorch.org/whl/cu128', bat)
        self.assertIn('https://download.pytorch.org/whl/cpu', bat)

    def test_bridge_replaces_upstream_mp3_only_loader(self):
        engine = (ROOT / "app" / "audio_engine.py").read_text(encoding="utf-8")
        bridge = (ROOT / "app" / "transkun_bridge.py").read_text(encoding="utf-8")
        self.assertIn('app.transkun_bridge', engine)
        self.assertIn('AudioSegment.from_file', bridge)
        self.assertNotIn('AudioSegment.from_mp3', bridge)
        self.assertIn('writeMidi', bridge)
        self.assertIn('--probe', bridge)

    def test_probe_requires_importable_runtime(self):
        source = (ROOT / "app" / "hifi_piano.py").read_text(encoding="utf-8")
        self.assertIn('import transkun.transcribe', source)
        self.assertIn('runtime is incomplete', source)

    def test_current_version_and_line_caps(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        server = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn('Piano Auto Player v0.6.21', html)
        self.assertIn('PianoAutoPlayer/0.6.21', server)
        for path in list((ROOT / 'app').glob('*.py')) + list((ROOT / 'web').glob('*.js')):
            self.assertLessEqual(len(path.read_text(encoding='utf-8').splitlines()), 450, str(path))


if __name__ == '__main__':
    unittest.main()
