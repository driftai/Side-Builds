from __future__ import annotations

import search_fusion as sf
from search_discovery import SearchResult


def _result(title: str, url: str, engine: str, rank: int) -> SearchResult:
    return SearchResult(title=title, url=url, snippet=f"{title} snippet", engine=engine, rank=rank)


def test_rrf_rewards_cross_engine_consensus_and_merges_tracking_variants(monkeypatch):
    rows = {
        "google": [
            _result("Only Google", "https://solo.example/item", "google", 1),
            _result("Shared", "https://www.shared.example/page?utm_source=google", "google", 2),
        ],
        "duckduckgo": [
            _result("Shared", "https://shared.example/page#details", "duckduckgo", 1),
            _result("Only DDG", "https://ddg.example/item", "duckduckgo", 2),
        ],
        "bing": [
            _result("Shared", "https://shared.example/page/", "bing", 1),
            _result("Only Bing", "https://bing.example/item", "bing", 2),
        ],
    }

    def fake_attempt(engine, query):
        return rows[engine], {"engine": engine, "query": query, "ok": True, "score": 0.8, "results_found": len(rows[engine])}

    monkeypatch.setattr(sf, "_attempt", fake_attempt)
    out, attempts = sf.discover_results_fused("shared thing", "google", target_count=4)

    assert len(attempts) == 3
    assert out[0].title == "Shared"
    meta = sf.fusion_metadata(out[0])
    assert meta["engine_consensus"] == 3
    assert set(meta["engine_ranks"]) == {"google", "duckduckgo", "bing"}
    assert meta["canonical_url"] == "https://shared.example/page"
    assert meta["fusion_score"] > sf.fusion_metadata(out[1])["fusion_score"]


def test_rrf_keeps_real_representative_url_for_fetching(monkeypatch):
    original = "https://www.example.com/path?keep=1&utm_source=x"

    def fake_attempt(engine, query):
        if engine == "google":
            return [_result("Example", original, engine, 1)], {"engine": engine, "ok": True, "score": 0.8, "results_found": 1}
        return [], {"engine": engine, "ok": True, "score": 0.8, "results_found": 0}

    monkeypatch.setattr(sf, "_attempt", fake_attempt)
    out, _ = sf.discover_results_fused("example", "google", target_count=2)

    assert out[0].url == original
    assert sf.fusion_metadata(out[0])["canonical_url"] == "https://example.com/path?keep=1"


def test_failed_engine_does_not_abort_fused_discovery(monkeypatch):
    def fake_attempt(engine, query):
        if engine == "google":
            return [], {"engine": engine, "ok": False, "error": "blocked", "results_found": 0}
        return [_result(f"{engine} result", f"https://{engine}.example/a", engine, 1)], {"engine": engine, "ok": True, "score": 0.7, "results_found": 1}

    monkeypatch.setattr(sf, "_attempt", fake_attempt)
    out, attempts = sf.discover_results_fused("test", "google", target_count=5)

    assert len(out) == 2
    assert any(not row["ok"] for row in attempts)
    assert {row.engine for row in out} == {"duckduckgo", "bing"}
