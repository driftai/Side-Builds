from __future__ import annotations

from fastapi.testclient import TestClient

from server import app


def _state() -> dict:
    return {
        "schema_version": 1,
        "next_space_id": 2,
        "spaces": [
            {
                "id": 1,
                "raw": "https://example.com",
                "status": "complete",
                "payload": {"data": {"identity": {"title": "Example Domain"}}, "report": "# Example Domain"},
                "history": [],
                "last_change": None,
            }
        ],
        "relationship_snapshot": {"stats": {"spaces": 1, "clusters": 0}},
    }


def test_saved_workspace_api_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOKMARK_INTEL_DATA_DIR", str(tmp_path))
    client = TestClient(app)

    created = client.post("/api/workspaces", json={"name": "API Workspace", "state": _state()})
    assert created.status_code == 200
    doc = created.json()
    workspace_id = doc["id"]

    listing = client.get("/api/workspaces")
    assert listing.status_code == 200
    assert listing.json()["workspaces"][0]["id"] == workspace_id

    loaded = client.get(f"/api/workspaces/{workspace_id}")
    assert loaded.status_code == 200
    assert loaded.json()["name"] == "API Workspace"
    assert loaded.json()["state"] == _state()

    deleted = client.delete(f"/api/workspaces/{workspace_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == workspace_id
    assert client.get(f"/api/workspaces/{workspace_id}").status_code == 404


def test_saved_workspace_api_rejects_invalid_workspace_id(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOOKMARK_INTEL_DATA_DIR", str(tmp_path))
    client = TestClient(app)
    response = client.get("/api/workspaces/not-a-uuid")
    assert response.status_code == 422
