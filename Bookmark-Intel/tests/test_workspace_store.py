from __future__ import annotations

import json

import pytest

from workspace_store import (
    MAX_SPACE_HISTORY,
    MAX_WORKSPACE_SPACES,
    WORKSPACE_SCHEMA,
    WORKSPACE_SCHEMA_VERSION,
    WorkspaceNotFoundError,
    WorkspaceStoreError,
    delete_workspace,
    list_workspaces,
    load_workspace,
    save_workspace,
    workspace_data_dir,
)


def _state() -> dict:
    return {
        "schema_version": 1,
        "next_space_id": 3,
        "spaces": [
            {
                "id": 1,
                "raw": "https://example.com",
                "status": "complete",
                "payload": {"data": {"identity": {"title": "Example Domain"}}, "report": "# Example Domain"},
                "history": [],
                "last_change": None,
            },
            {
                "id": 2,
                "raw": "Attack on Titan",
                "status": "complete",
                "payload": {"data": {"identity": {"title": "Attack on Titan"}}, "report": "# Attack on Titan"},
                "history": [],
                "last_change": None,
            },
        ],
        "relationship_snapshot": {"stats": {"spaces": 2, "clusters": 0}},
    }


def test_workspace_store_round_trip_and_overwrite(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOKMARK_INTEL_DATA_DIR", str(tmp_path))
    first = save_workspace("Anime Research", _state())

    assert workspace_data_dir() == tmp_path.resolve()
    assert first["schema"] == WORKSPACE_SCHEMA
    assert first["schema_version"] == WORKSPACE_SCHEMA_VERSION
    assert first["name"] == "Anime Research"
    assert load_workspace(first["id"])["state"] == _state()

    rows = list_workspaces()
    assert len(rows) == 1
    assert rows[0]["id"] == first["id"]
    assert rows[0]["space_count"] == 2

    updated = save_workspace("Anime Research Updated", _state(), first["id"])
    assert updated["id"] == first["id"]
    assert updated["created_at"] == first["created_at"]
    assert load_workspace(first["id"])["name"] == "Anime Research Updated"


def test_workspace_delete_and_missing_id(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOKMARK_INTEL_DATA_DIR", str(tmp_path))
    doc = save_workspace("Disposable", _state())
    delete_workspace(doc["id"])
    assert list_workspaces() == []
    with pytest.raises(WorkspaceNotFoundError):
        load_workspace(doc["id"])


def test_workspace_ids_cannot_escape_store_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOKMARK_INTEL_DATA_DIR", str(tmp_path))
    with pytest.raises(WorkspaceStoreError):
        load_workspace("../../outside")
    with pytest.raises(WorkspaceStoreError):
        save_workspace("Bad id", _state(), "..\\outside")


def test_workspace_validation_rejects_bad_names_and_too_many_spaces(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOKMARK_INTEL_DATA_DIR", str(tmp_path))
    with pytest.raises(WorkspaceStoreError):
        save_workspace("bad\x00name", _state())

    oversized = _state()
    oversized["spaces"] = [{"id": i} for i in range(MAX_WORKSPACE_SPACES + 1)]
    with pytest.raises(WorkspaceStoreError):
        save_workspace("Too Many", oversized)


def test_workspace_validation_rejects_transient_duplicate_and_unbounded_history(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOKMARK_INTEL_DATA_DIR", str(tmp_path))

    transient = _state()
    transient["spaces"][0]["status"] = "working"
    with pytest.raises(WorkspaceStoreError):
        save_workspace("Transient", transient)

    duplicate = _state()
    duplicate["spaces"][1]["id"] = 1
    with pytest.raises(WorkspaceStoreError):
        save_workspace("Duplicate", duplicate)

    history = _state()
    history["spaces"][0]["history"] = [{"captured_at": str(i), "payload": {}} for i in range(MAX_SPACE_HISTORY + 1)]
    with pytest.raises(WorkspaceStoreError):
        save_workspace("History", history)


def test_workspace_reader_rejects_wrong_schema(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOKMARK_INTEL_DATA_DIR", str(tmp_path))
    directory = tmp_path / "workspaces"
    directory.mkdir(parents=True)
    bad_id = "11111111-1111-1111-1111-111111111111"
    (directory / f"{bad_id}.json").write_text(json.dumps({"schema": "other", "schema_version": 1, "state": _state()}), encoding="utf-8")
    with pytest.raises(WorkspaceStoreError):
        load_workspace(bad_id)
