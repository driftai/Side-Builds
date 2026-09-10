from __future__ import annotations

from server import (
    APP_VERSION,
    load_changes_js,
    load_disclosure_js,
    load_persistence_js,
    load_relationships_js,
    load_ui,
    load_workspace_js,
)


def test_workspace_ui_exposes_independent_collapsible_spaces() -> None:
    html = load_ui()
    js = load_workspace_js()

    assert APP_VERSION == "0.10.0"
    assert 'id="spaces"' in html
    assert 'class="spaces"' in html
    assert "createPendingSpace" in js
    assert "completeSpace" in js
    assert "space.open=false" in js
    assert 'id="expand-all"' in html
    assert 'id="collapse-all"' in html
    assert 'id="clear-all"' in html
    assert "spaces.appendChild(space)" in js
    assert "workspaceState" in js


def test_workspace_accepts_and_splits_batch_input() -> None:
    html = load_ui()
    js = load_workspace_js()

    assert '<textarea id="url"' in html
    assert "parseTargets" in js
    assert "text.split('\\n')" in js
    assert "runBatch" in js
    assert "MAX_PARALLEL=3" in js
    assert "Promise.all(workers)" in js
    assert "Ctrl/Cmd + Enter" in html


def test_workspace_supports_bracketed_bulk_search_terms() -> None:
    html = load_ui()
    js = load_workspace_js()

    assert "[Attack On Titan] [Bleach] [Dragon Ball]" in html
    assert "Bulk search terms use [square brackets]" in html
    assert "const tokenRe=" in js
    assert "match[1]" in js
    assert "explicit.length" in js
    assert "explicit.sort((a,b)=>a.index-b.index)" in js
    assert "if(/^\\s*\\(\\s*https?:\\/\\//i.test(after))continue" in js


def test_workspace_keeps_single_analysis_api_contract_per_target() -> None:
    js = load_workspace_js()

    assert "fetch('/api/analyze'" in js
    assert "JSON.stringify({url:raw})" in js
    assert "renderResult(payload)" in js
    assert "Readable report" in js
    assert "Raw JSON" in js


def test_workspace_relationship_layer_is_non_destructive_and_evidence_backed() -> None:
    html = load_ui()
    ui_js = load_workspace_js()
    graph_js = load_relationships_js()

    assert 'id="workspace-intel"' in html
    assert 'id="workspace-intel-content"' in html
    assert '/workspace_relationships.js' in html
    assert '/workspace_ui.js' in html
    assert "analyzeWorkspace" in graph_js
    assert "duplicate_resource" in graph_js
    assert "same_subject" in graph_js
    assert "derived_source" in graph_js
    assert "related_subject" in graph_js
    assert "sourceRanking" in graph_js
    assert "agreements" in graph_js
    assert "conflicts" in graph_js
    assert "searchWarnings" in graph_js
    assert "subject_relevance_score" in graph_js
    assert "query_match_score" in graph_js
    assert "renderWorkspaceIntel" in ui_js
    assert "Corroborated facts" in ui_js
    assert "Disagreements / variants" in ui_js
    assert "Search-source quality warnings" in ui_js
    assert "Focus spaces" in ui_js


def test_workspace_intelligence_disclosures_default_collapsed() -> None:
    html = load_ui()
    disclosure_js = load_disclosure_js()

    assert '/workspace_disclosure.js' in html
    assert "workspace-intel.disclosure-collapsed" in disclosure_js
    assert "setCollapsed(node,true)" in disclosure_js
    assert "querySelectorAll('.cluster-card')" in disclosure_js
    assert "querySelectorAll('.intel-warning')" in disclosure_js
    assert "querySelectorAll('.intel-section')" in disclosure_js
    assert "MutationObserver" in disclosure_js
    assert "aria-expanded" in disclosure_js


def test_compact_workspace_manager_exposes_persistence_controls() -> None:
    html = load_ui()
    persistence_js = load_persistence_js()

    assert 'id="workspace-manager"' in html
    assert 'id="workspace-name"' in html
    assert 'id="workspace-save"' in html
    assert 'id="workspace-saved"' in html
    assert 'id="workspace-load"' in html
    assert 'id="workspace-refresh-all"' in html
    assert 'id="workspace-export-json"' in html
    assert 'id="workspace-export-md"' in html
    assert 'id="workspace-export-html"' in html
    assert 'id="workspace-import"' in html
    assert '/workspace_persistence.js' in html
    assert "jsonFetch('/api/workspaces')" in persistence_js
    assert "serializeWorkspace" in persistence_js
    assert "restoreWorkspace" in persistence_js
    assert "application/json" in persistence_js
    assert "text/markdown" in persistence_js
    assert "text/html" in persistence_js
    assert "URL.createObjectURL" in persistence_js
    assert "URL.revokeObjectURL" in persistence_js


def test_refresh_change_detection_preserves_history_and_updates_same_space() -> None:
    html = load_ui()
    ui_js = load_workspace_js()
    changes_js = load_changes_js()

    assert '/workspace_changes.js' in html
    assert "comparePayloads" in changes_js
    assert "semanticSnapshot" in changes_js
    assert "MAX_CHANGES=80" in changes_js
    assert "refreshSpaceById" in ui_js
    assert "refreshAll" in ui_js
    assert "MAX_HISTORY=5" in ui_js
    assert "history=[...(state.history||[])" in ui_js
    assert "last_change" in ui_js
    assert "since previous capture" in ui_js
    assert "change${Number(changeSet.count)===1?'':'s'}" in ui_js
    assert 'class="space-refresh"' in ui_js


def test_workspace_snapshot_preserves_relationships_without_reanalysis_on_restore() -> None:
    ui_js = load_workspace_js()

    assert "relationship_snapshot:getRelationshipGraph()" in ui_js
    assert "serializeWorkspace" in ui_js
    assert "restoreWorkspace" in ui_js
    assert "Workspace restored." in ui_js
    assert "loaded without re-analysis" in ui_js
    assert "window.BookmarkWorkspace=" in ui_js
