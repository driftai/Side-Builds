from __future__ import annotations

import ast
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "freetoken"
PATCH = ROOT / "runtime-patches" / "freetoken" / "15-qwen3-coder-fp8.patch"
UPSTREAM_SHA = "0ab982f10905fa775962a4eddcb44caa50065251"
PATCH_SHA256 = "5d7d34e1fdf2c041e3eab9fbf8a9c086d51005374ad83b87f8c5387d35e2ece1"
EXPECTED_FILES = {
    "python/freetoken/models/qwen3_moe/__init__.py",
    "python/freetoken/models/qwen3_moe/attention.py",
    "python/freetoken/models/qwen3_moe/config.py",
    "python/freetoken/models/qwen3_moe/moe.py",
    "python/freetoken/models/qwen3_moe/weight.py",
}


def run(*command: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)


class Qwen3CoderFp8ApprovedPatchCase(unittest.TestCase):
    def test_approved_patch_is_exact_and_applies_cleanly_to_pinned_freetoken(self) -> None:
        self.assertTrue(PATCH.is_file(), f"approved patch missing: {PATCH}")
        self.assertEqual(hashlib.sha256(PATCH.read_bytes()).hexdigest(), PATCH_SHA256)
        with tempfile.TemporaryDirectory(prefix="qwen3-coder-fp8-", dir="/tmp") as tmp:
            work = Path(tmp) / "freetoken"
            clone = run("git", "clone", "--quiet", "--no-hardlinks", str(RUNTIME), str(work), cwd=ROOT)
            self.assertEqual(clone.returncode, 0, clone.stderr)
            checkout = run("git", "checkout", "--quiet", "--detach", UPSTREAM_SHA, cwd=work)
            self.assertEqual(checkout.returncode, 0, checkout.stderr)

            check = run("git", "apply", "--check", "--whitespace=nowarn", str(PATCH), cwd=work)
            self.assertEqual(check.returncode, 0, check.stderr)
            apply = run("git", "apply", "--whitespace=nowarn", str(PATCH), cwd=work)
            self.assertEqual(apply.returncode, 0, apply.stderr)

            changed = run("git", "diff", "--name-only", "HEAD", "--", cwd=work)
            self.assertEqual(changed.returncode, 0, changed.stderr)
            self.assertEqual(set(changed.stdout.splitlines()), EXPECTED_FILES)

            diff_check = run("git", "diff", "--check", cwd=work)
            self.assertEqual(diff_check.returncode, 0, diff_check.stdout or diff_check.stderr)

            for relative in EXPECTED_FILES:
                source = (work / relative).read_text(encoding="utf-8")
                ast.parse(source, filename=relative)

            config_text = (work / "python/freetoken/models/qwen3_moe/config.py").read_text()
            attention_text = (work / "python/freetoken/models/qwen3_moe/attention.py").read_text()
            weight_text = (work / "python/freetoken/models/qwen3_moe/weight.py").read_text()
            self.assertIn('return "fp8_block", block_size', config_text)
            self.assertIn("make_col_merged", attention_text)
            self.assertIn("setup_offload_expert_banks", weight_text)
            self.assertIn('ExpertBanks("fp8_block"', weight_text)


if __name__ == "__main__":
    unittest.main()
