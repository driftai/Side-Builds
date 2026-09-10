from __future__ import annotations

from search_synthesis import finalize_search_synthesis


def _source(url, title, kind, summary, relevance, *, quality=0.9, role="source", tags=None, fusion=0.5, consensus=1):
    return {
        "url": url,
        "title": title,
        "role": "organic",
        "status": "ok",
        "curation_role": role,
        "subject_relevance_score": relevance,
        "query_match_score": relevance,
        "fusion_score": fusion,
        "engine_consensus": consensus,
        "analysis": {
            "title": title,
            "kind": kind,
            "summary": summary,
            "quality_score": quality,
            "tags": tags or [],
        },
    }


def _cyberpunk_bundle():
    article = "https://www.cbr.com/cyberpunk-best-underrated-retro-anime/"
    fandom = "https://www.fandom.com/articles/10-best-cyberpunk-anime"
    sources = [
        _source(
            article,
            "These Retro Cyberpunk Anime Are Underrated But Amazing",
            "article",
            "The 1980s and 1990s were goldmines of dark cyberpunk anime and OVAs exploring technology and dystopia.",
            0.64,
            quality=0.98,
            tags=["anime", "cyberpunk", "retro"],
            fusion=0.66,
            consensus=2,
        ),
        _source(
            fandom,
            "The 10 Best Cyberpunk Anime",
            "video",
            "Paramount Pictures previews the live-action Ghost in the Shell movie starring Scarlett Johansson in five short videos.",
            0.62,
            quality=0.93,
            role="community_wiki",
            tags=["anime", "video", "ghost-in-the-shell"],
            fusion=0.35,
            consensus=1,
        ),
    ]
    return {
        "input": {"query": "obscure 1990s cyberpunk anime"},
        "classification": {"kind": "web_search_research"},
        "summary": sources[1]["analysis"]["summary"],
        "tags": ["web-search", "research", "anime", "video"],
        "key_facts": [
            {"label": "Organic sources selected", "value": "2/5"},
            {"label": "Sources analyzed successfully", "value": "2/2"},
            {"label": "Wikipedia reference", "value": "attempted / unavailable"},
            {"label": "Fandom reference", "value": "selected"},
            {"label": "Duration", "value": "0:43 (1 source)"},
        ],
        "bookmark": {},
        "sections": {"search_research": {}},
        "quality": {"extraction_score": 0.8},
        "search_research": {
            "query": "obscure 1990s cyberpunk anime",
            "sources_succeeded": 2,
            "sources": sources,
            "compiled_facts": [
                {"label": "Duration", "values": [{"value": "0:43", "source_count": 1, "sources": [fandom]}]},
                {"label": "Uploader", "values": [{"value": "Zuleika B", "source_count": 1, "sources": [fandom]}]},
                {"label": "Genres", "values": [{"value": "Cyberpunk", "source_count": 1, "sources": [article]}]},
            ],
        },
    }


def test_embedded_video_cannot_hijack_article_topic_overview_or_facts():
    data = finalize_search_synthesis(_cyberpunk_bundle())
    research = data["search_research"]
    fandom = next(row for row in research["sources"] if "fandom.com" in row["url"])

    assert fandom["embedded_content_risk"] is True
    assert fandom["synthesis_eligible"] is False
    assert "Paramount Pictures" not in data["summary"]
    assert "1990s" in data["summary"]
    assert research["overview_source"].startswith("https://www.cbr.com/")
    assert {row["label"] for row in research["compiled_facts"]}.isdisjoint({"Duration", "Uploader"})
    assert research["synthesis"]["warning_count"] >= 1


def test_source_ranking_and_synthesis_signals_exist_for_single_search():
    data = finalize_search_synthesis(_cyberpunk_bundle())
    research = data["search_research"]
    labels = {row["label"] for row in data["key_facts"]}

    assert research["source_ranking"][0]["synthesis_eligible"] is True
    assert research["synthesis"]["strategy"].startswith("RRF retrieval")
    assert "Synthesis confidence" in labels
    assert "Evidence-eligible sources" in labels
    assert "Top research source" in labels
    assert data["sections"]["search_research"]["synthesis_version"] == 1


def test_native_video_query_can_keep_video_specific_evidence():
    url = "https://www.youtube.com/watch?v=abc"
    source = _source(
        url,
        "Ghost in the Shell trailer video",
        "video",
        "Official Ghost in the Shell trailer video and preview.",
        0.92,
        role="watch_stream",
        tags=["video", "trailer"],
        fusion=0.8,
        consensus=2,
    )
    data = {
        "input": {"query": "Ghost in the Shell trailer video"},
        "classification": {"kind": "web_search_research"},
        "summary": source["analysis"]["summary"],
        "tags": [],
        "key_facts": [],
        "bookmark": {},
        "sections": {"search_research": {}},
        "quality": {"extraction_score": 0.8},
        "search_research": {
            "query": "Ghost in the Shell trailer video",
            "sources_succeeded": 1,
            "sources": [source],
            "compiled_facts": [
                {"label": "Duration", "values": [{"value": "2:30", "source_count": 1, "sources": [url]}]},
            ],
        },
    }
    out = finalize_search_synthesis(data)
    labels = {row["label"] for row in out["search_research"]["compiled_facts"]}
    assert "Duration" in labels
    assert out["search_research"]["sources"][0]["primary_content_confidence"] >= 0.9


def test_low_evidence_source_remains_provenance_but_cannot_supply_fact():
    bad = _source(
        "https://unrelated.example/page",
        "Unrelated page",
        "article",
        "Something unrelated to the requested topic.",
        0.2,
        quality=0.8,
        fusion=0.1,
    )
    data = {
        "input": {"query": "Attack on Titan"},
        "classification": {"kind": "web_search_research"},
        "summary": bad["analysis"]["summary"],
        "tags": [],
        "key_facts": [],
        "bookmark": {},
        "sections": {"search_research": {}},
        "quality": {"extraction_score": 0.5},
        "search_research": {
            "query": "Attack on Titan",
            "sources_succeeded": 1,
            "sources": [bad],
            "compiled_facts": [{"label": "Year", "values": [{"value": "1956", "source_count": 1, "sources": [bad["url"]]}]}],
        },
    }
    out = finalize_search_synthesis(data)
    assert out["search_research"]["sources"][0]["synthesis_eligible"] is False
    assert out["search_research"]["compiled_facts"] == []
    assert out["search_research"]["synthesis"]["warning_count"] == 1


def test_non_search_resource_is_unchanged():
    direct = {"classification": {"kind": "article"}, "summary": "Direct URL"}
    assert finalize_search_synthesis(direct) is direct
