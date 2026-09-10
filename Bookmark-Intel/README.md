# Bookmark Intel

Local-first URL intelligence and browser-search research workspace.

Bookmark Intel analyzes public URLs and search phrases, preserves source evidence, scores extraction quality, and keeps every result in an independent workspace space. It can batch URLs and bracketed search terms, relate results without merging their original reports, persist research sessions, and refresh them later for meaningful changes.

## Current capabilities — v0.10

- Progressive public-URL acquisition: bounded HTTP -> Lightpanda when available -> Camoufox when needed.
- URL classification and page-specific metadata/content/entity/link extraction.
- Browser-search research for plain phrases and search-engine URLs.
- Multi-engine search discovery using Reciprocal Rank Fusion across Google, DuckDuckGo and Bing result sets.
- Query-focused evidence reranking after source pages are analyzed.
- Page-primary safeguards so embedded media/interstitial content cannot silently become the parent page's subject evidence.
- One shared evidence score drives overview selection, fact promotion, synthesis warnings and the provenance fields consumed by Workspace Intelligence.
- Batch input with independent result spaces.
  - URLs identify themselves normally.
  - Multiple search terms on one line use brackets: `[Attack On Titan] [Bleach] [Dragon Ball]`.
- Single-search and bulk-search parity: every term goes through the same `/api/analyze` retrieval -> curation -> precision -> synthesis path. Only truly cross-space features require multiple completed spaces.
- Workspace Intelligence above the original spaces:
  - conservative same-subject clustering;
  - duplicate/canonical resource detection;
  - search-source provenance;
  - corroborated facts and disagreements;
  - source ranking and suspicious-source warnings.
- Named saved workspaces.
- Reload/resume without re-running completed analyses.
- Full-fidelity JSON export/import.
- Readable Markdown and standalone HTML dossier export.
- Refresh one space or every completed space and surface meaningful changes since the previous capture.
- Five previous captures retained per refreshed space for bounded history.

The extraction textbox and result spaces remain the primary UI. Workspace management and relationship intelligence are compact/collapsible supporting controls.

## Search intelligence pipeline

Every search term, whether submitted alone or as one member of a bracketed batch, follows the same product path:

```text
search term
  -> Google / DuckDuckGo / Bing discovery
  -> canonical result identity + Reciprocal Rank Fusion
  -> bounded source selection
  -> normal Bookmark Intel URL analysis for each selected source
  -> existing search curation
  -> existing precision filtering
  -> shared evidence-aware synthesis
  -> result space / relationships / persistence / change detection / exports
```

The synthesis pass keeps provenance even when evidence is rejected. A weak, blocked, interstitial, or embedded-media source can remain visible as a discovered/analyzed source while being marked ineligible to supply the compiled overview or subject facts.

This specifically prevents cases such as an article page with an embedded video from donating the video's duration/uploader/description as though those were facts about the article's searched subject. Native video searches remain eligible for video-specific facts when the query actually has video intent.

Search result data includes retrieval consensus, evidence score, primary-content confidence, synthesis eligibility, source ranking, synthesis confidence, and source-quality warnings. Workspace Intelligence consumes the same relevance/query/provenance fields rather than maintaining a separate competing relevance system.

## Run

Open a terminal in the public project folder:

```text
Side-Builds/Bookmark-Intel
```

Launch:

```bat
START.bat
```

UI:

```text
http://127.0.0.1:9077
```

## Input examples

One URL:

```text
https://www.python.org/
```

One browser-search phrase:

```text
Code Geass
```

Mixed batch:

```text
https://atsu.moe/manga/u1cn
[Player of the Fallen Noble Family] [Attack On Titan]
https://en.wikipedia.org/wiki/Attack_on_Titan
```

## Saved workspace storage

Saved workspaces are intentionally stored outside the Git checkout so normal research does not dirty the repository.

Default locations:

- Windows: `%LOCALAPPDATA%\BookmarkIntel\workspaces`
- Linux/macOS-style fallback: `$XDG_DATA_HOME/bookmark-intel/workspaces` or `~/.local/share/bookmark-intel/workspaces`

Override for testing or custom placement:

```text
BOOKMARK_INTEL_DATA_DIR
```

Workspace files use application-generated UUID filenames. The displayed workspace name is metadata, not a filesystem path.

The local save format is versioned JSON (`bookmark-intel-workspace`, schema version 1), bounded to 500 spaces and roughly 25 MB per saved workspace. Writes use a temporary sibling file plus atomic replacement.

## Refresh / change detection

Refreshing re-runs the existing `/api/analyze` path for the same URL or search phrase and updates the same workspace space. Search refreshes therefore receive the same fused retrieval and evidence-aware synthesis as first-run searches.

The previous successful result is kept in history before replacement. A failed refresh leaves the prior successful capture intact.

The change detector compares semantic result fields rather than raw acquisition internals. It watches title/type/category, summary, key facts and dynamic sections, compiled search facts, tags/entities, selected links, and meaningful extraction-quality changes. Because synthesis confidence/top-source/warnings feed the normal semantic result, research-quality changes can surface through the same refresh history rather than a separate subsystem.

## Export / import

- **JSON** — full-fidelity workspace export, including spaces, result payloads, search synthesis evidence, refresh history, last detected changes, and a relationship snapshot. JSON is the supported import format.
- **Markdown** — readable compiled dossier. Search reports include synthesis strategy, evidence ranking and source-quality warnings.
- **HTML** — standalone dark-theme readable dossier built from the same readable reports.

Loading a saved workspace or importing JSON restores existing captures without fetching the web again. Relationships are recomputed from the restored canonical spaces; the saved relationship snapshot remains in the JSON archive for provenance.

## Browser fallbacks

### Lightpanda

Optional. If a `lightpanda` executable is on `PATH`, Bookmark Intel can use it before Camoufox for weak JavaScript pages.

### Camoufox

`camoufox>=0.5,<0.6` is installed in the project environment. If its browser runtime is missing, fetch it once:

```powershell
.\.venv\Scripts\python.exe -m camoufox fetch
```

Browser request routing keeps the public-only network boundary and explicitly settles Playwright routes before teardown to avoid cancellation-noise races.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

JavaScript syntax checks:

```powershell
node --check workspace_relationships.js
node --check workspace_ui.js
node --check workspace_disclosure.js
node --check workspace_changes.js
node --check workspace_persistence.js
```

The project has a recursive 450-physical-line Python house guard. `intel_legacy.py` is the sole grandfathered exemption.

## Architecture

Core URL extraction remains independent from workspace/product features, while search intelligence is shared through the normal product entrypoint.

- `intel.py` / `analysis_pipeline.py` — stable analyzer orchestration and concrete resource pipeline.
- `acquisition*.py` — safe progressive URL acquisition and browser rendering.
- `search_discovery.py` — search-page parsing and input targeting.
- `search_fusion.py` — canonical cross-engine result identity and Reciprocal Rank Fusion.
- `search_research.py` / `search_compile.py` — bounded research bundle and source extraction.
- `search_curation*.py` / `search_precision.py` — deterministic subject curation and precision cleanup.
- `search_synthesis.py` — final shared evidence ranking, page-primary filtering, overview/fact synthesis and warnings.
- `workspace_relationships.js` — non-destructive cross-space intelligence consuming the hardened per-search provenance fields.
- `workspace_changes.js` — semantic refresh comparison.
- `workspace_ui.js` — batch input, result-space lifecycle, restore/refresh state.
- `workspace_disclosure.js` — compact disclosure behavior.
- `workspace_persistence.js` — named workspace controls and browser import/export.
- `workspace_store.py` — durable local JSON workspace library.
- `server.py` — local FastAPI product entrypoint, synthesis/report finalization, asset serving, CLI, and saved-workspace endpoints.

## Public-only boundary

Bookmark Intel is for public pages. It does not attempt to defeat authentication, paywalls, or private access controls. URL validation rejects loopback, private, link-local, reserved, multicast, unspecified and CGNAT destinations. Browser routing also blocks non-public network destinations.
