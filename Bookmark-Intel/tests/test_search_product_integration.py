from __future__ import annotations

import server


def _search_bundle() -> dict:
    url = "https://docs.example.com/widget"
    return {
        "input": {"query": "Widget API docs"},
        "classification": {"kind": "web_search_research"},
        "summary": "Widget API documentation and examples.",
        "tags": [],
        "key_facts": [
            {"label": "Organic sources selected", "value": "1/5"},
            {"label": "Sources analyzed successfully", "value": "1/1"},
        ],
        "bookmark": {},
        "sections": {"search_research": {}},
        "quality": {"extraction_score": 0.8},
        "search_research": {
            "query": "Widget API docs",
            "sources_succeeded": 1,
            "sources": [
                {
                    "url": url,
                    "title": "Widget API docs",
                    "role": "organic",
                    "status": "ok",
                    "curation_role": "docs",
                    "subject_relevance_score": 0.9,
                    "query_match_score": 0.98,
                    "fusion_score": 0.8,
                    "engine_consensus": 2,
                    "analysis": {
                        "title": "Widget API docs",
                        "kind": "documentation",
                        "summary": "Widget API documentation and examples.",
                        "quality_score": 0.9,
                        "tags": ["api", "documentation"],
                    },
                }
            ],
            "compiled_facts": [],
        },
    }


def test_product_finalizer_gives_every_search_synthesis_fields():
    data = server._finalize_product_intelligence(_search_bundle())
    assert data["search_research"]["synthesis"]["version"] == 1
    assert data["search_research"]["source_ranking"]
    assert data["sections"]["search_research"]["synthesis_confidence"] > 0
    assert any(row["label"] == "Synthesis confidence" for row in data["key_facts"])


def test_product_report_exports_same_synthesis_evidence_seen_in_live_result():
    data = server._finalize_product_intelligence(_search_bundle())
    report = server._render_product_report(data)
    assert "## Search synthesis" in report
    assert "Evidence-ranked sources" in report
    assert "Synthesis confidence" in report


def test_refresh_change_detector_tracks_search_synthesis_evidence():
    js = server.load_changes_js()
    assert "search_synthesis.confidence" in js
    assert "search_synthesis.top_source" in js
    assert "search_synthesis.warnings" in js
    assert "search_synthesis.ranking" in js


def test_direct_url_payload_is_unchanged_by_product_search_finalizer():
    direct = {"classification": {"kind": "article"}, "summary": "Direct resource"}
    assert server._finalize_product_intelligence(direct) is direct
