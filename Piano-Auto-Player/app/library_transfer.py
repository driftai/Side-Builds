from __future__ import annotations

import io
import json
import re
import time
import zipfile
from pathlib import Path
from typing import Any

from .library import SongLibrary

_FORMAT_SONG = "piano-auto-player-song"
_FORMAT_LIBRARY = "piano-auto-player-library"
_SCHEMA = 1
_MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
_MAX_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
_MAX_JSON_BYTES = 25 * 1024 * 1024
_MAX_SONGS = 2000


def safe_filename(value: str, fallback: str = "song") -> str:
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", str(value or "")).strip(" ._")
    return (name[:120] or fallback).strip()


def export_song_bytes(song: dict[str, Any]) -> tuple[bytes, str]:
    payload = {"format": _FORMAT_SONG, "schema": _SCHEMA, "song": song}
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    return body, f"{safe_filename(song.get('title') or song.get('id') or 'song')}.piano-song.json"


def export_library_zip(library: SongLibrary, ids: list[str] | None = None) -> tuple[bytes, str, int]:
    wanted = {str(item) for item in (ids or []) if str(item)}
    songs = [song for song in library.list() if not wanted or str(song.get("id")) in wanted]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    manifest = {
        "format": _FORMAT_LIBRARY,
        "schema": _SCHEMA,
        "exported_at": time.time(),
        "song_count": len(songs),
        "songs": [],
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, song in enumerate(songs, 1):
            song_id = safe_filename(song.get("id") or f"song-{index}", f"song-{index}")
            path = f"songs/{index:04d}-{song_id}.json"
            manifest["songs"].append({"id": song.get("id"), "title": song.get("title"), "file": path})
            archive.writestr(path, json.dumps({"format": _FORMAT_SONG, "schema": _SCHEMA, "song": song}, ensure_ascii=False, indent=2))
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    label = "all" if not wanted else f"selected-{len(songs)}"
    return buffer.getvalue(), f"Piano-Auto-Player-library-{label}-{stamp}.zip", len(songs)


def import_library_bytes(library: SongLibrary, raw: bytes, filename: str = "") -> dict[str, Any]:
    if len(raw) > _MAX_ARCHIVE_BYTES:
        raise ValueError("Import is too large (100 MB maximum compressed input).")
    lower = str(filename or "").lower()
    if raw[:4] == b"PK\x03\x04" or lower.endswith(".zip"):
        records = _records_from_zip(raw)
    else:
        records = [_record_from_json(raw)]
    imported = 0
    updated = 0
    existing = {str(song.get("id")) for song in library.list()}
    errors: list[str] = []
    for index, record in enumerate(records, 1):
        try:
            song_id = str(record.get("id") or "")
            if song_id and song_id in existing:
                updated += 1
            library.save(record)
            imported += 1
            if song_id:
                existing.add(song_id)
        except Exception as exc:
            errors.append(f"Song {index}: {exc}")
    if not imported and errors:
        raise ValueError(errors[0])
    return {"imported": imported, "updated": updated, "errors": errors[:20]}


def _record_from_json(raw: bytes) -> dict[str, Any]:
    if len(raw) > _MAX_JSON_BYTES:
        raise ValueError("Individual song JSON is too large.")
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid song JSON: {exc}") from exc
    if isinstance(payload, dict) and isinstance(payload.get("song"), dict):
        payload = payload["song"]
    if not isinstance(payload, dict):
        raise ValueError("Song import must contain a JSON object.")
    if not str(payload.get("sheet") or "").strip() and not payload.get("performance"):
        raise ValueError("Imported song has no sheet or timed performance.")
    return payload


def _records_from_zip(raw: bytes) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    total = 0
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw), "r")
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid library ZIP.") from exc
    with archive:
        entries = [item for item in archive.infolist() if not item.is_dir() and item.filename.startswith("songs/") and item.filename.lower().endswith(".json")]
        if len(entries) > _MAX_SONGS:
            raise ValueError(f"Library ZIP contains more than {_MAX_SONGS} song files.")
        for item in entries:
            total += int(item.file_size)
            if total > _MAX_UNCOMPRESSED_BYTES:
                raise ValueError("Library ZIP expands beyond the 250 MB safety limit.")
            if item.file_size > _MAX_JSON_BYTES:
                raise ValueError(f"Song file is too large: {Path(item.filename).name}")
            records.append(_record_from_json(archive.read(item)))
    if not records:
        raise ValueError("Library ZIP does not contain any song JSON files.")
    return records
