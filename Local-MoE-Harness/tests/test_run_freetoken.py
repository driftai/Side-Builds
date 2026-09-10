from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class RunFreeTokenTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        (self.root / ".venvs" / "freetoken" / "bin").mkdir(parents=True)
        shutil.copy2(
            PROJECT_ROOT / "scripts" / "run-freetoken.sh",
            self.root / "scripts" / "run-freetoken.sh",
        )
        shutil.copy2(
            PROJECT_ROOT / "scripts" / "runtime-env-linux.sh",
            self.root / "scripts" / "runtime-env-linux.sh",
        )
        cuda_root = self.root / ".venvs" / "freetoken" / "lib" / "nvidia" / "cu13"
        (cuda_root / "bin").mkdir(parents=True)
        (cuda_root / "include").mkdir()
        (cuda_root / "lib").mkdir()
        fake_python = self.root / ".venvs" / "freetoken" / "bin" / "python"
        fake_python.write_text(
            f"#!/usr/bin/env bash\nprintf '%s\\n' '{cuda_root}'\n",
            encoding="utf-8",
        )
        fake_python.chmod(0o755)
        (cuda_root / "include" / "cuda_runtime.h").write_text("", encoding="utf-8")
        (cuda_root / "lib" / "libcudart.so.13").write_text("", encoding="utf-8")
        fake_nvcc = cuda_root / "bin" / "nvcc"
        fake_nvcc.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        fake_nvcc.chmod(0o755)
        fake_ft = self.root / ".venvs" / "freetoken" / "bin" / "ft"
        fake_ft.write_text(
            "#!/usr/bin/env bash\n"
            "printf 'HOST_CXX=%s\\n' \"${FREETOKEN_GGUF_HOST_CXX:-}\"\n",
            encoding="utf-8",
        )
        fake_ft.chmod(0o755)
        self.bin_dir = self.root / "test-bin"
        self.bin_dir.mkdir()
        fake_cxx = self.bin_dir / "g++-12"
        fake_cxx.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        fake_cxx.chmod(0o755)

    def tearDown(self):
        self.temp.cleanup()

    def _run(self, model_path: str) -> str:
        env = os.environ.copy()
        env.pop("FREETOKEN_GGUF_HOST_CXX", None)
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        result = subprocess.run(
            [str(self.root / "scripts" / "run-freetoken.sh"), model_path, "1919"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_gguf_launch_selects_supported_gcc_12(self):
        output = self._run("/models/example.gguf")
        self.assertIn(f"HOST_CXX={self.bin_dir / 'g++-12'}", output)

    def test_directory_launch_does_not_change_host_compiler(self):
        output = self._run("/models/example-directory")
        self.assertIn("HOST_CXX=\n", output)


if __name__ == "__main__":
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    if result.wasSuccessful():
        print(f"[FreeToken Launcher Tests] PASS ({result.testsRun}/{result.testsRun})")
        raise SystemExit(0)
    print("\n".join(stream.getvalue().splitlines()[-40:]), file=sys.stderr)
    raise SystemExit(1)
