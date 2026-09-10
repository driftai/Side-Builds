from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from intel import AnalyzeError, analyze_input, render_markdown
from search_synthesis import finalize_search_synthesis, render_search_synthesis_markdown
from workspace_store import (
    WorkspaceNotFoundError,
    WorkspaceStoreError,
    delete_workspace,
    list_workspaces,
    load_workspace,
    save_workspace,
)

APP_VERSION = "0.10.0"
ROOT = Path(__file__).resolve().parent
UI_PATH = ROOT / "ui.html"
WORKSPACE_JS_PATH = ROOT / "workspace_ui.js"
RELATIONSHIPS_JS_PATH = ROOT / "workspace_relationships.js"
DISCLOSURE_JS_PATH = ROOT / "workspace_disclosure.js"
CHANGES_JS_PATH = ROOT / "workspace_changes.js"
PERSISTENCE_JS_PATH = ROOT / "workspace_persistence.js"

app = FastAPI(title="Bookmark Intel POC", version=APP_VERSION)
log = logging.getLogger("bookmark-intel")


class AnalyzeRequest(BaseModel):
    # Kept as `url` for API/UI backward compatibility, but the value may now be either
    # one public URL or one browser-search phrase.
    url: str


class WorkspaceSaveRequest(BaseModel):
    id: str | None = None
    name: str
    state: dict[str, Any]


def _load_asset(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        log.exception("Failed to load Bookmark Intel %s from %s", label, path)
        raise HTTPException(status_code=500, detail=f"Bookmark Intel {label} is unavailable.") from exc


def load_ui() -> str:
    return _load_asset(UI_PATH, "UI")


def load_workspace_js() -> str:
    return _load_asset(WORKSPACE_JS_PATH, "workspace UI")


def load_relationships_js() -> str:
    return _load_asset(RELATIONSHIPS_JS_PATH, "relationship engine")


def load_disclosure_js() -> str:
    return _load_asset(DISCLOSURE_JS_PATH, "workspace disclosure controls")


def load_changes_js() -> str:
    return _load_asset(CHANGES_JS_PATH, "workspace change detector")


def load_persistence_js() -> str:
    return _load_asset(PERSISTENCE_JS_PATH, "workspace persistence controls")


def _finalize_product_intelligence(data: dict[str, Any]) -> dict[str, Any]:
    """Apply product-level search intelligence identically to single and batch jobs."""
    return finalize_search_synthesis(data)


def _render_product_report(data: dict[str, Any]) -> str:
    report = render_markdown(data).rstrip()
    synthesis = render_search_synthesis_markdown(data).strip()
    return report + ("\n\n" + synthesis if synthesis else "") + "\n"


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return load_ui()


@app.get("/workspace_ui.js")
def workspace_js() -> Response:
    return Response(content=load_workspace_js(), media_type="application/javascript")


@app.get("/workspace_relationships.js")
def relationships_js() -> Response:
    return Response(content=load_relationships_js(), media_type="application/javascript")


@app.get("/workspace_disclosure.js")
def disclosure_js() -> Response:
    return Response(content=load_disclosure_js(), media_type="application/javascript")


@app.get("/workspace_changes.js")
def changes_js() -> Response:
    return Response(content=load_changes_js(), media_type="application/javascript")


@app.get("/workspace_persistence.js")
def persistence_js() -> Response:
    return Response(content=load_persistence_js(), media_type="application/javascript")


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest) -> dict:
    try:
        data = _finalize_product_intelligence(analyze_input(request.url))
    except AnalyzeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("Unexpected analyzer failure for %s", request.url)
        raise HTTPException(status_code=500, detail="Unexpected analyzer failure. Check the local server log for details.") from exc
    return {"data": data, "report": _render_product_report(data)}


@app.get("/api/workspaces")
def saved_workspaces() -> dict:
    try:
        return {"workspaces": list_workspaces()}
    except WorkspaceStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/workspaces/{workspace_id}")
def get_saved_workspace(workspace_id: str) -> dict:
    try:
        return load_workspace(workspace_id)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkspaceStoreError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/workspaces")
def put_saved_workspace(request: WorkspaceSaveRequest) -> dict:
    try:
        return save_workspace(request.name, request.state, request.id)
    except WorkspaceStoreError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.delete("/api/workspaces/{workspace_id}")
def remove_saved_workspace(workspace_id: str) -> dict:
    try:
        delete_workspace(workspace_id)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkspaceStoreError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"deleted": workspace_id}


def cli() -> None:
    parser = argparse.ArgumentParser(description="Analyze one public bookmark URL or compile one browser-search phrase.")
    parser.add_argument("url", nargs="?", help="Public http(s) URL, Google/Bing/DDG search URL, or plain search phrase")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of the readable report")
    parser.add_argument("--save", type=Path, help="Write the selected output to a file")
    parser.add_argument("--serve", action="store_true", help="Start the local browser UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9077)
    args = parser.parse_args()

    if args.serve or not args.url:
        print(f"Bookmark Intel POC v{APP_VERSION}: http://{args.host}:{args.port}")
        uvicorn.run("server:app", host=args.host, port=args.port, reload=False)
        return

    try:
        data = _finalize_product_intelligence(analyze_input(args.url))
    except AnalyzeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    output = json.dumps(data, indent=2, ensure_ascii=False) if args.json else _render_product_report(data)
    if args.save:
        args.save.write_text(output, encoding="utf-8")
        print(f"Saved {args.save}")
    else:
        print(output)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cli()
