#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME = ROOT / "runtime" / "freetoken"
DEFAULT_PATCH_DIR = ROOT / "runtime-patches" / "freetoken"
DEFAULT_MANIFEST = DEFAULT_PATCH_DIR / "manifest.json"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class PatchSpec:
    file: str
    sha256: str
    purpose: str


@dataclass(frozen=True)
class Contract:
    upstream_sha: str
    patches: tuple[PatchSpec, ...]
    rejected_patches: tuple[str, ...]


def _run(
    command: list[str],
    *,
    cwd: Path | None = None,
    check: bool = False,
    text: bool = True,
) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=text,
        check=False,
    )
    if check and proc.returncode != 0:
        stderr = proc.stderr.strip() if text else proc.stderr.decode(errors="replace").strip()
        stdout = proc.stdout.strip() if text else proc.stdout.decode(errors="replace").strip()
        detail = stderr or stdout or f"exit code {proc.returncode}"
        raise ContractError(f"Command failed: {' '.join(command)}: {detail}")
    return proc


def _git(runtime_dir: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    return _run(["git", "-C", str(runtime_dir), *args], check=check)


def _safe_patch_name(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.endswith(".patch"):
        raise ContractError(f"{label} must be a .patch filename.")
    if Path(value).name != value or value in {".", ".."}:
        raise ContractError(f"{label} must not contain a directory: {value!r}.")
    return value


def load_contract(manifest_path: Path, patch_dir: Path) -> Contract:
    if not manifest_path.is_file():
        raise ContractError(f"Approved patch manifest is missing: {manifest_path}")
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"Approved patch manifest is unreadable: {exc}") from exc

    if data.get("schema_version") != 1:
        raise ContractError("Approved patch manifest schema_version must be 1.")
    upstream_sha = str(data.get("upstream_sha", "")).lower()
    if not SHA_RE.fullmatch(upstream_sha):
        raise ContractError("Approved patch manifest upstream_sha must be a full 40-character SHA.")

    raw_patches = data.get("patches")
    if not isinstance(raw_patches, list) or not raw_patches:
        raise ContractError("Approved patch manifest must contain a non-empty patches list.")

    patches: list[PatchSpec] = []
    approved_names: list[str] = []
    for index, item in enumerate(raw_patches):
        if not isinstance(item, dict):
            raise ContractError(f"Manifest patches[{index}] must be an object.")
        name = _safe_patch_name(item.get("file"), f"Manifest patches[{index}].file")
        digest = str(item.get("sha256", "")).lower()
        if not SHA256_RE.fullmatch(digest):
            raise ContractError(f"Manifest SHA256 is invalid for {name}.")
        purpose = item.get("purpose", "")
        if not isinstance(purpose, str):
            raise ContractError(f"Manifest purpose must be text for {name}.")
        if name in approved_names:
            raise ContractError(f"Approved patch is listed more than once: {name}")
        approved_names.append(name)
        patches.append(PatchSpec(name, digest, purpose))

    raw_rejected = data.get("rejected_patches", [])
    if not isinstance(raw_rejected, list):
        raise ContractError("Manifest rejected_patches must be a list.")
    rejected = tuple(
        _safe_patch_name(name, "Rejected patch entry") for name in raw_rejected
    )
    if len(set(rejected)) != len(rejected):
        raise ContractError("Manifest rejected_patches contains duplicates.")
    overlap = sorted(set(approved_names) & set(rejected))
    if overlap:
        raise ContractError(f"Patches cannot be both approved and rejected: {', '.join(overlap)}")

    if not patch_dir.is_dir():
        raise ContractError(f"Approved patch directory is missing: {patch_dir}")
    present = {path.name for path in patch_dir.glob("*.patch") if path.is_file()}
    approved = set(approved_names)
    missing = sorted(approved - present)
    extra = sorted(present - approved)
    if missing:
        raise ContractError(f"Approved patch file is missing: {', '.join(missing)}")
    if extra:
        rejected_extra = sorted(set(extra) & set(rejected))
        if rejected_extra:
            raise ContractError(f"Rejected/unapproved patch present: {', '.join(rejected_extra)}")
        raise ContractError(f"Unapproved patch present: {', '.join(extra)}")

    for patch in patches:
        path = patch_dir / patch.file
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != patch.sha256:
            raise ContractError(
                f"Patch SHA256 mismatch for {patch.file}: expected {patch.sha256}, got {actual}"
            )

    return Contract(upstream_sha, tuple(patches), rejected)


def verify_head(runtime_dir: Path, expected_sha: str) -> str:
    if not runtime_dir.is_dir():
        raise ContractError(f"FreeToken runtime directory is missing: {runtime_dir}")
    head = _git(runtime_dir, "rev-parse", "HEAD")
    if head.returncode != 0:
        raise ContractError(f"FreeToken runtime is not a Git checkout: {runtime_dir}")
    actual = head.stdout.strip().lower()
    if actual != expected_sha:
        raise ContractError(f"FreeToken HEAD mismatch: expected {expected_sha}, got {actual}")
    return actual


def _patch_state(runtime_dir: Path, patch_path: Path) -> str:
    forward = _git(
        runtime_dir,
        "apply",
        "--check",
        "--ignore-whitespace",
        "--whitespace=nowarn",
        str(patch_path),
    )
    if forward.returncode == 0:
        return "pending"

    reverse = _git(
        runtime_dir,
        "apply",
        "--check",
        "-R",
        "--ignore-whitespace",
        "--whitespace=nowarn",
        str(patch_path),
    )
    if reverse.returncode == 0:
        return "already_applied"

    forward_detail = (forward.stderr or forward.stdout).strip()
    reverse_detail = (reverse.stderr or reverse.stdout).strip()
    detail = forward_detail or reverse_detail or "no Git diagnostic"
    raise ContractError(
        f"Patch is partially applied or inconsistent: {patch_path.name}. {detail}"
    )


def _apply_one(runtime_dir: Path, patch_path: Path) -> None:
    _git(
        runtime_dir,
        "apply",
        "--ignore-whitespace",
        "--whitespace=nowarn",
        str(patch_path),
        check=True,
    )


def _diff_bytes(runtime_dir: Path) -> bytes:
    proc = _run(
        [
            "git",
            "-C",
            str(runtime_dir),
            "diff",
            "--binary",
            "--full-index",
            "--no-ext-diff",
            "--no-color",
            "HEAD",
            "--",
        ],
        text=False,
    )
    if proc.returncode != 0:
        raise ContractError("Could not calculate the FreeToken working-tree diff.")
    return proc.stdout


def _build_expected_runtime(
    source_runtime: Path,
    patch_dir: Path,
    contract: Contract,
    destination: Path,
) -> None:
    _run(
        [
            "git",
            "clone",
            "--quiet",
            "--no-hardlinks",
            "--no-checkout",
            str(source_runtime),
            str(destination),
        ],
        check=True,
    )
    _git(destination, "checkout", "--quiet", "--detach", contract.upstream_sha, check=True)
    for patch in contract.patches:
        patch_path = patch_dir / patch.file
        check = _git(destination, "apply", "--check", "--whitespace=nowarn", str(patch_path))
        if check.returncode != 0:
            detail = (check.stderr or check.stdout).strip() or "no Git diagnostic"
            raise ContractError(
                f"Approved patch does not apply to upstream {contract.upstream_sha}: "
                f"{patch.file}. {detail}"
            )
        _git(destination, "apply", "--whitespace=nowarn", str(patch_path), check=True)


def verify_runtime(
    runtime_dir: Path,
    patch_dir: Path,
    manifest_path: Path,
) -> dict:
    contract = load_contract(manifest_path, patch_dir)
    head = verify_head(runtime_dir, contract.upstream_sha)

    diff_check = _git(runtime_dir, "diff", "--check")
    if diff_check.returncode != 0:
        detail = (diff_check.stdout or diff_check.stderr).strip()
        raise ContractError(f"FreeToken diff failed git diff --check: {detail}")

    untracked = _git(runtime_dir, "ls-files", "--others", "--exclude-standard", check=True)
    untracked_files = [line for line in untracked.stdout.splitlines() if line.strip()]
    if untracked_files:
        preview = ", ".join(untracked_files[:8])
        suffix = " ..." if len(untracked_files) > 8 else ""
        raise ContractError(f"Untracked FreeToken files detected: {preview}{suffix}")

    with tempfile.TemporaryDirectory(prefix="local-moe-freetoken-verify-", dir="/tmp") as tmp:
        expected_dir = Path(tmp) / "expected"
        _build_expected_runtime(runtime_dir, patch_dir, contract, expected_dir)
        expected_diff = _diff_bytes(expected_dir)
        actual_diff = _diff_bytes(runtime_dir)

    expected_hash = hashlib.sha256(expected_diff).hexdigest()
    actual_hash = hashlib.sha256(actual_diff).hexdigest()
    if actual_diff != expected_diff:
        modified = _git(runtime_dir, "diff", "--name-status", "HEAD", "--", check=True)
        paths = "; ".join(modified.stdout.splitlines()[:12]) or "no tracked diff"
        raise ContractError(
            "Runtime differs from approved patch baseline: "
            f"expected diff sha256 {expected_hash}, got {actual_hash}; {paths}"
        )

    modified = _git(runtime_dir, "diff", "--name-only", "HEAD", "--", check=True)
    modified_files = tuple(line for line in modified.stdout.splitlines() if line.strip())
    return {
        "head": head,
        "patch_count": len(contract.patches),
        "diff_sha256": actual_hash,
        "modified_files": modified_files,
        "untracked_count": 0,
    }


def apply_contract(
    runtime_dir: Path,
    patch_dir: Path,
    manifest_path: Path,
) -> tuple[list[tuple[str, str]], dict]:
    contract = load_contract(manifest_path, patch_dir)
    verify_head(runtime_dir, contract.upstream_sha)
    initial_states = [
        (patch.file, _patch_state(runtime_dir, patch_dir / patch.file))
        for patch in contract.patches
    ]
    for name, state in initial_states:
        if state == "pending":
            _apply_one(runtime_dir, patch_dir / name)
    states = [
        (name, "applied" if state == "pending" else state)
        for name, state in initial_states
    ]
    result = verify_runtime(runtime_dir, patch_dir, manifest_path)
    return states, result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Enforce the approved FreeToken patch contract.")
    parser.add_argument("action", choices=("apply", "verify"))
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--patch-dir", type=Path, default=DEFAULT_PATCH_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    started = time.perf_counter()
    try:
        if args.action == "apply":
            states, result = apply_contract(args.runtime_dir, args.patch_dir, args.manifest)
            if args.verbose:
                for name, state in states:
                    print(f"[FreeToken Patch] {name}: {state.replace('_', ' ')}")
            applied = sum(state == "applied" for _, state in states)
            already = sum(state == "already_applied" for _, state in states)
            print(
                f"[FreeToken Patch] Result: APPROVED {result['patch_count']}-PATCH BASELINE "
                f"(applied={applied}, already_applied={already})"
            )
        else:
            result = verify_runtime(args.runtime_dir, args.patch_dir, args.manifest)
            if args.verbose:
                print(f"[FreeToken Verify] Upstream SHA: PASS ({result['head']})")
                print(f"[FreeToken Verify] Approved patch manifest: PASS ({result['patch_count']})")
                print(f"[FreeToken Verify] Runtime combined diff: PASS ({result['diff_sha256']})")
                print("[FreeToken Verify] Untracked files: PASS")
                print("[FreeToken Verify] Rejected patch behavior: PASS")
            elapsed = time.perf_counter() - started
            print(
                f"[FreeToken Verify] Result: APPROVED {result['patch_count']}-PATCH BASELINE "
                f"({elapsed:.2f}s)"
            )
    except ContractError as exc:
        prefix = "FreeToken Patch" if args.action == "apply" else "FreeToken Verify"
        print(f"[{prefix}] ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
