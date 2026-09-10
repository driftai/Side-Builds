from __future__ import annotations

import argparse
import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

HUNK_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)
ALLOWED_PATCH_PREFIX = "python/freetoken/models/qwen3_moe/"


@dataclass(frozen=True)
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: tuple[str, ...]


@dataclass(frozen=True)
class FilePatch:
    old_path: str
    new_path: str
    hunks: tuple[Hunk, ...]


class PatchError(RuntimeError):
    pass


def _count(value: str | None) -> int:
    return 1 if value is None else int(value)


def _header_path(value: str, prefix: str) -> str:
    path = value.split("\t", 1)[0].strip()
    if path.startswith(prefix):
        path = path[len(prefix):]
    return path


def parse_unified_diff(text: str) -> tuple[FilePatch, ...]:
    lines = text.splitlines()
    patches: list[FilePatch] = []
    index = 0

    while index < len(lines):
        if not lines[index].startswith("--- "):
            index += 1
            continue

        old_path = _header_path(lines[index][4:], "a/")
        index += 1
        if index >= len(lines) or not lines[index].startswith("+++ "):
            raise PatchError(f"Missing +++ header after {old_path}")
        new_path = _header_path(lines[index][4:], "b/")
        index += 1

        hunks: list[Hunk] = []
        while index < len(lines) and not lines[index].startswith("--- "):
            line = lines[index]
            if not line.startswith("@@ "):
                index += 1
                continue

            match = HUNK_RE.match(line)
            if match is None:
                raise PatchError(f"Invalid hunk header: {line}")
            index += 1

            hunk_lines: list[str] = []
            while index < len(lines):
                current = lines[index]
                if current.startswith("@@ ") or current.startswith("--- "):
                    break
                if current == r"\ No newline at end of file":
                    index += 1
                    continue
                if not current or current[0] not in {" ", "+", "-"}:
                    raise PatchError(f"Unsupported unified-diff line: {current!r}")
                hunk_lines.append(current)
                index += 1

            hunks.append(
                Hunk(
                    old_start=int(match.group("old_start")),
                    old_count=_count(match.group("old_count")),
                    new_start=int(match.group("new_start")),
                    new_count=_count(match.group("new_count")),
                    lines=tuple(hunk_lines),
                )
            )

        if not hunks:
            raise PatchError(f"No hunks found for {new_path}")
        patches.append(FilePatch(old_path, new_path, tuple(hunks)))

    if not patches:
        raise PatchError("No file patches found")
    return tuple(patches)


def _target_relative_path(path: str) -> Path:
    normalized = path.replace("\\", "/")
    if not normalized.startswith(ALLOWED_PATCH_PREFIX):
        raise PatchError(
            f"Refusing patch target outside {ALLOWED_PATCH_PREFIX}: {path}"
        )
    relative = normalized.removeprefix("python/")
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise PatchError(f"Unsafe patch path: {path}")
    return candidate


def apply_file_patch(source_text: str, patch: FilePatch) -> str:
    source = source_text.splitlines()
    output: list[str] = []
    cursor = 0

    for hunk in patch.hunks:
        old_index = hunk.old_start - 1
        if old_index < cursor or old_index > len(source):
            raise PatchError(
                f"Invalid hunk location for {patch.new_path}: {hunk.old_start}"
            )

        output.extend(source[cursor:old_index])
        cursor = old_index
        old_seen = 0
        new_seen = 0

        for line in hunk.lines:
            marker = line[0]
            expected = line[1:]
            if marker in {" ", "-"}:
                if cursor >= len(source) or source[cursor] != expected:
                    actual = source[cursor] if cursor < len(source) else "<EOF>"
                    raise PatchError(
                        f"Patch context mismatch in {patch.new_path} at source line "
                        f"{cursor + 1}: expected {expected!r}, got {actual!r}"
                    )
                if marker == " ":
                    output.append(expected)
                    new_seen += 1
                cursor += 1
                old_seen += 1
            elif marker == "+":
                output.append(expected)
                new_seen += 1

        if old_seen != hunk.old_count or new_seen != hunk.new_count:
            raise PatchError(
                f"Hunk count mismatch in {patch.new_path}: "
                f"old {old_seen}/{hunk.old_count}, new {new_seen}/{hunk.new_count}"
            )

    output.extend(source[cursor:])
    trailing_newline = source_text.endswith(("\n", "\r"))
    return "\n".join(output) + ("\n" if trailing_newline else "")


def apply_patch(site_packages: Path, patch_path: Path, expected_sha256: str) -> list[Path]:
    patch_bytes = patch_path.read_bytes()
    actual_hash = hashlib.sha256(patch_bytes).hexdigest()
    if actual_hash.lower() != expected_sha256.lower():
        raise PatchError(
            f"Patch SHA-256 mismatch: expected {expected_sha256}, got {actual_hash}"
        )

    file_patches = parse_unified_diff(patch_bytes.decode("utf-8"))
    prepared: list[tuple[Path, str]] = []

    for file_patch in file_patches:
        if file_patch.old_path != file_patch.new_path:
            raise PatchError(
                "Renames are not supported by this compatibility applier: "
                f"{file_patch.old_path} -> {file_patch.new_path}"
            )
        relative = _target_relative_path(file_patch.new_path)
        target = (site_packages / relative).resolve()
        root = site_packages.resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise PatchError(f"Patch target escapes site-packages: {target}") from exc

        if not target.is_file():
            raise PatchError(f"Required FreeToken source file is missing: {target}")
        original = target.read_text(encoding="utf-8")
        prepared.append((target, apply_file_patch(original, file_patch)))

    for target, updated in prepared:
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(updated)
            os.replace(temporary_name, target)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    return [target for target, _ in prepared]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Strictly apply the approved Qwen3-MoE Windows compatibility patch "
            "to a project-local FreeToken installation without requiring Git."
        )
    )
    parser.add_argument("--site-packages", required=True, type=Path)
    parser.add_argument("--patch", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()

    try:
        changed = apply_patch(
            args.site_packages.resolve(),
            args.patch.resolve(),
            args.expected_sha256,
        )
    except (OSError, UnicodeError, PatchError) as exc:
        print(f"[Windows patch] ERROR: {exc}")
        return 1

    for path in changed:
        print(f"[Windows patch] Patched {path}")
    print(f"[Windows patch] Applied {len(changed)} verified FreeToken source files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
