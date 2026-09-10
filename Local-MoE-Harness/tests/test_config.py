import io
import sys
import unittest

from app.config import load_settings


class ConfigTests(unittest.TestCase):
    def test_settings_have_runtime_url(self):
        settings = load_settings()
        self.assertTrue(settings["runtime_base_url"].startswith("http"))
        self.assertTrue(settings["model_root"])


if __name__ == "__main__":
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    if result.wasSuccessful():
        print(f"[Config Tests] PASS ({result.testsRun}/{result.testsRun})")
        raise SystemExit(0)
    print("\n".join(stream.getvalue().splitlines()[-40:]), file=sys.stderr)
    raise SystemExit(1)
