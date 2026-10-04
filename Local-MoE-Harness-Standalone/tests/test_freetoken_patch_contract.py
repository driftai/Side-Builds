from __future__ import annotations

import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import freetoken_patch_contract as contract  # noqa: E402


ACTIVE_RUNTIME = ROOT / "runtime" / "freetoken"
PATCH_DIR = ROOT / "runtime-patches" / "freetoken"
MANIFEST = PATCH_DIR / "manifest.json"
EXPECTED_FILES = {
    "python/freetoken/attention/fi.py",
    "python/freetoken/core.py",
    "python/freetoken/engine/engine.py",
    "python/freetoken/engine/sample.py",
    "python/freetoken/kernel/triton/activation.py",
    "python/freetoken/kernel/triton/fp8_pertensor_linear.py",
    "python/freetoken/layers/activation.py",
    "python/freetoken/models/qwen3_moe/__init__.py",
    "python/freetoken/models/qwen3_moe/attention.py",
    "python/freetoken/models/qwen3_moe/config.py",
    "python/freetoken/models/qwen3_moe/moe.py",
    "python/freetoken/models/qwen3_moe/weight.py",
}


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
    )


class TemporaryContractCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="local-moe-contract-test-", dir="/tmp")
        self.root = Path(self.temp.name)
        self.runtime = self.root / "runtime"
        self.patch_dir = self.root / "patches"
        subprocess.run(
            ["git", "clone", "--quiet", "--no-hardlinks", str(ACTIVE_RUNTIME), str(self.runtime)],
            check=True,
            capture_output=True,
            text=True,
        )
        shutil.copytree(PATCH_DIR, self.patch_dir)
        manifest_contract = contract.load_contract(MANIFEST, PATCH_DIR)
        git(self.runtime, "checkout", "--quiet", "--detach", manifest_contract.upstream_sha)
        self.manifest = self.patch_dir / "manifest.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def apply(self):
        return contract.apply_contract(self.runtime, self.patch_dir, self.manifest)

    def verify(self):
        return contract.verify_runtime(self.runtime, self.patch_dir, self.manifest)

    def test_reconstruction_and_idempotency(self) -> None:
        first_states, first = self.apply()
        self.assertEqual({state for _, state in first_states}, {"applied"})
        self.assertEqual(set(first["modified_files"]), EXPECTED_FILES)
        first_diff = contract._diff_bytes(self.runtime)

        second_states, second = self.apply()
        self.assertEqual({state for _, state in second_states}, {"already_applied"})
        self.assertEqual(first["diff_sha256"], second["diff_sha256"])
        self.assertEqual(first_diff, contract._diff_bytes(self.runtime))
        self.assertFalse(git(self.runtime, "ls-files", "--others", "--exclude-standard").stdout)
        self.assertEqual(git(self.runtime, "diff", "--check").returncode, 0)

    def test_changed_upstream_sha_is_rejected(self) -> None:
        git(self.runtime, "-c", "user.name=Contract Test", "-c", "user.email=test@local", "commit", "--allow-empty", "-m", "drift")
        with self.assertRaisesRegex(contract.ContractError, "HEAD mismatch"):
            self.verify()

    def test_missing_approved_patch_is_rejected(self) -> None:
        (self.patch_dir / "01-triton-sampling.patch").unlink()
        with self.assertRaisesRegex(contract.ContractError, "Approved patch file is missing"):
            self.verify()

    def test_changed_patch_hash_is_rejected(self) -> None:
        path = self.patch_dir / "01-triton-sampling.patch"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaisesRegex(contract.ContractError, "SHA256 mismatch"):
            self.verify()

    def test_partially_applied_patch_is_rejected(self) -> None:
        patch = self.patch_dir / "02-fi-triton-prefill.patch"
        pieces = patch.read_text(encoding="utf-8").split("\n@@ ", 2)
        self.assertEqual(len(pieces), 3)
        partial = self.root / "partial.patch"
        partial.write_text(pieces[0] + "\n@@ " + pieces[1] + "\n", encoding="utf-8")
        git(self.runtime, "apply", str(partial))
        before = contract._diff_bytes(self.runtime)
        with self.assertRaisesRegex(contract.ContractError, "partially applied or inconsistent"):
            self.apply()
        self.assertEqual(before, contract._diff_bytes(self.runtime))

    def test_extra_source_edit_is_rejected(self) -> None:
        self.apply()
        target = self.runtime / "python" / "freetoken" / "core.py"
        target.write_text(target.read_text(encoding="utf-8") + "\n# contract drift\n", encoding="utf-8")
        with self.assertRaisesRegex(contract.ContractError, "differs from approved patch baseline"):
            self.verify()

    def test_untracked_runtime_file_is_rejected(self) -> None:
        self.apply()
        (self.runtime / "UNTRACKED_CONTRACT_DRIFT.txt").write_text("drift\n", encoding="utf-8")
        with self.assertRaisesRegex(contract.ContractError, "Untracked FreeToken files"):
            self.verify()

    def test_extra_patch_file_is_rejected(self) -> None:
        (self.patch_dir / "99-unapproved.patch").write_text("not approved\n", encoding="utf-8")
        with self.assertRaisesRegex(contract.ContractError, "Unapproved patch present"):
            self.verify()

    def test_rejected_patch_filename_is_rejected(self) -> None:
        (self.patch_dir / "04-offload-kernels-pt.patch").write_text("rejected\n", encoding="utf-8")
        with self.assertRaisesRegex(contract.ContractError, "Rejected/unapproved patch present"):
            self.verify()


class ActiveRuntimeCase(unittest.TestCase):
    def test_active_runtime_matches_contract(self) -> None:
        result = contract.verify_runtime(ACTIVE_RUNTIME, PATCH_DIR, MANIFEST)
        self.assertEqual(result["patch_count"], 8)
        self.assertEqual(set(result["modified_files"]), EXPECTED_FILES)


if __name__ == "__main__":
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    if result.wasSuccessful():
        print(f"[FreeToken Contract Tests] PASS ({result.testsRun}/{result.testsRun})")
        raise SystemExit(0)
    lines = stream.getvalue().splitlines()
    print("\n".join(lines[-40:]), file=sys.stderr)
    raise SystemExit(1)
