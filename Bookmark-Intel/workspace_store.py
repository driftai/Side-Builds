from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

WORKSPACE_SCHEMA = "bookmark-intel-workspace"
WORKSPACE_SCHEMA_VERSION = 1
MAX_WORKSPACE_BYTES = 25_000_000
MAX_WORKSPACE_SPACES = 500
MAX_WORKSPACE_NAME_CHARS = 120
MAX_SPACE_HISTORY = 5
_SAFE_NAME_RE = re.compile(r"[\x00-\x1f\x7f]")


class WorkspaceStoreError(ValueError):
    pass


class WorkspaceNotFoundError(WorkspaceStoreError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def workspace_data_dir() -> Path:
    override = os.environ.get("BOOKMARK_INTEL_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "BookmarkIntel"
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return base / "bookmark-intel"


def workspace_dir() -> Path:
    return workspace_data_dir() / "workspaces"


def _normalize_id(value: str | None) -> str:
    if not value:
        return str(uuid4())
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise WorkspaceStoreError("Workspace id is invalid.") from exc
    canonical = str(parsed)
    if canonical != str(value).casefold():
        raise WorkspaceStoreError("Workspace id must use canonical UUID form.")
    return canonical


def _clean_name(value: Any) -> str:
    name = re.sub(r"\s+", " ", str(value or "")).strip()
    if not name:
        raise WorkspaceStoreError("Workspace name is required.")
    if len(name) > MAX_WORKSPACE_NAME_CHARS:
        raise WorkspaceStoreError(f"Workspace name exceeds {MAX_WORKSPACE_NAME_CHARS} characters.")
    if _SAFE_NAME_RE.search(name):
        raise WorkspaceStoreError("Workspace name contains unsupported control characters.")
    return name


def _path_for(workspace_id: str) -> Path:
    canonical = _normalize_id(workspace_id)
    return workspace_dir() / f"{canonical}.json"


def _validate_space(space: Any, seen_ids: set[int]) -> None:
    if not isinstance(space, dict):
        raise WorkspaceStoreError("Workspace spaces must be JSON objects.")
    space_id = space.get("id")
    if isinstance(space_id, bool) or not isinstance(space_id, int) or space_id < 1:
        raise WorkspaceStoreError("Workspace contains an invalid space id.")
    if space_id in seen_ids:
        raise WorkspaceStoreError("Workspace contains duplicate space ids.")
    seen_ids.add(space_id)

    status = space.get("status")
    if status not in {"complete", "failed"}:
        raise WorkspaceStoreError("Only complete or failed spaces may be persisted.")
    if status == "complete":
        payload = space.get("payload")
        if not isinstance(payload, dict):
            raise WorkspaceStoreError("Completed workspace space is missing its result payload.")
        if not isinstance(payload.get("data"), dict) or not isinstance(payload.get("report"), str):
            raise WorkspaceStoreError("Completed workspace payload must contain data and report fields.")
    history = space.get("history", [])
    if not isinstance(history, list):
        raise WorkspaceStoreError("Workspace space history must be an array.")
    if len(history) > MAX_SPACE_HISTORY:
        raise WorkspaceStoreError(f"Workspace space history exceeds the {MAX_SPACE_HISTORY}-capture limit.")


def validate_workspace_state(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise WorkspaceStoreError("Workspace state must be a JSON object.")
    spaces = state.get("spaces")
    if not isinstance(spaces, list):
        raise WorkspaceStoreError("Workspace state must contain a spaces array.")
    if len(spaces) > MAX_WORKSPACE_SPACES:
        raise WorkspaceStoreError(f"Workspace exceeds the {MAX_WORKSPACE_SPACES}-space limit.")
    seen_ids: set[int] = set()
    for space in spaces:
        _validate_space(space, seen_ids)
    next_space_id = state.get("next_space_id", 1)
    if isinstance(next_space_id, bool) or not isinstance(next_space_id, int) or next_space_id < 1:
        raise WorkspaceStoreError("Workspace next_space_id is invalid.")
    if seen_ids and next_space_id <= max(seen_ids):
        raise WorkspaceStoreError("Workspace next_space_id must be greater than every persisted space id.")
    snapshot = state.get("relationship_snapshot")
    if snapshot is not None and not isinstance(snapshot, dict):
        raise WorkspaceStoreError("Workspace relationship snapshot must be an object.")
    try:
        encoded = json.dumps(state, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise WorkspaceStoreError("Workspace contains data that cannot be serialized as JSON.") from exc
    if len(encoded) > MAX_WORKSPACE_BYTES:
        raise WorkspaceStoreError(f"Workspace exceeds the {MAX_WORKSPACE_BYTES // 1_000_000} MB save limit.")
    return state


def _read_document(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise WorkspaceNotFoundError("Saved workspace was not found.") from exc
    except OSError as exc:
        raise WorkspaceStoreError(f"Could not read saved workspace: {exc}") from exc
    if len(raw) > MAX_WORKSPACE_BYTES + 1_000_000:
        raise WorkspaceStoreError("Saved workspace is larger than the supported limit.")
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkspaceStoreError("Saved workspace is not valid UTF-8 JSON.") from exc
    if not isinstance(doc, dict) or doc.get("schema") != WORKSPACE_SCHEMA:
        raise WorkspaceStoreError("Saved file is not a Bookmark Intel workspace.")
    if int(doc.get("schema_version") or 0) != WORKSPACE_SCHEMA_VERSION:
        raise WorkspaceStoreError("Saved workspace schema version is not supported.")
    doc["name"] = _clean_name(doc.get("name"))
    validate_workspace_state(doc.get("state"))
    return doc


def save_workspace(name: str, state: dict[str, Any], workspace_id: str | None = None) -> dict[str, Any]:
    name = _clean_name(name)
    state = validate_workspace_state(state)
    workspace_id = _normalize_id(workspace_id)
    directory = workspace_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{workspace_id}.json"
    now = _utc_now()
    created_at = now
    if path.exists():
        try:
            created_at = str(_read_document(path).get("created_at") or now)
        except WorkspaceStoreError:
            created_at = now
    document = {
        "schema": WORKSPACE_SCHEMA,
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "id": workspace_id,
        "name": name,
        "created_at": created_at,
        "updated_at": now,
        "state": state,
    }
    payload = json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")
    if len(payload) > MAX_WORKSPACE_BYTES + 1_000_000:
        raise WorkspaceStoreError("Serialized workspace exceeds the supported save limit.")
    temp = directory / f".{workspace_id}.{uuid4().hex}.tmp"
    try:
        with temp.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except OSError as exc:
        raise WorkspaceStoreError(f"Could not save workspace: {exc}") from exc
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
    return document


def load_workspace(workspace_id: str) -> dict[str, Any]:
    return _read_document(_path_for(workspace_id))


def list_workspaces() -> list[dict[str, Any]]:
    directory = workspace_dir()
    if not directory.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in directory.glob("*.json"):
        try:
            doc = _read_document(path)
        except WorkspaceStoreError:
            continue
        state = doc.get("state") or {}
        spaces = state.get("spaces") or []
        rows.append({
            "id": doc["id"],
            "name": doc["name"],
            "created_at": doc.get("created_at"),
            "updated_at": doc.get("updated_at"),
            "space_count": len(spaces),
        })
    rows.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    return rows


def delete_workspace(workspace_id: str) -> None:
    path = _path_for(workspace_id)
    try:
        path.unlink()
    except FileNotFoundError as exc:
        raise WorkspaceNotFoundError("Saved workspace was not found.") from exc
    except OSError as exc:
        raise WorkspaceStoreError(f"Could not delete workspace: {exc}") from exc
