from __future__ import annotations

import search_research as sr


def _result(title: str, url: str, engine: str = "google", rank: int = 1):
    return sr.SearchResult(title=title, url=url, snippet=f"Snippet for {title}", engine=engine, rank=rank)


def test_plain_phrase_enters_search_mode():
    target = sr.parse_input_target("Attack on Titan")
    assert target.mode == "search"
    assert target.query == "Attack on Titan"
    assert target.preferred_engine == "google"


def test_google_bing_duckduckgo_urls_extract_query():
    cases = [
        ("https://www.google.com/search?q=Attack%20on%20Titan", "google"),
        ("https://www.bing.com/search?q=Attack%20on%20Titan", "bing"),
        ("https://duckduckgo.com/?q=Attack%20on%20Titan", "duckduckgo"),
    ]
    for url, engine in cases:
        target = sr.parse_input_target(url)
        assert target.mode == "search"
        assert target.query == "Attack on Titan"
        assert target.preferred_engine == engine


def test_normal_and_bare_urls_stay_url_mode():
    a = sr.parse_input_target("https://example.com/page")
    b = sr.parse_input_target("example.com/page")
    assert a.mode == "url" and a.url == "https://example.com/page"
    assert b.mode == "url" and b.url == "https://example.com/page"


def test_extract_google_results_unwraps_redirect_and_filters_google_internal():
    html = """
    <html><body>
      <a href="/url?q=https%3A%2F%2Fexample.com%2Fa"><h3>Example A</h3></a>
      <a href="https://www.google.com/search?q=more"><h3>Internal Google</h3></a>
      <a href="https://example.org/b"><h3>Example B</h3></a>
    </body></html>
    """
    rows = sr.extract_search_results(html, "google", "https://www.google.com/search?q=test")
    assert [x.title for x in rows] == ["Example A", "Example B"]
    assert rows[0].url == "https://example.com/a"


def test_five_organic_plus_wikipedia_and_fandom_are_separate_slots():
    rows = [
        _result("Wikipedia", "https://en.wikipedia.org/wiki/Attack_on_Titan", rank=1),
        _result("A", "https://a.example/a", rank=2),
        _result("Fandom", "https://attackontitan.fandom.com/wiki/Attack_on_Titan_Wiki", rank=3),
        _result("B", "https://b.example/b", rank=4),
        _result("C", "https://c.example/c", rank=5),
        _result("D", "https://d.example/d", rank=6),
        _result("E", "https://e.example/e", rank=7),
        _result("F", "https://f.example/f", rank=8),
    ]
    selected = sr.select_source_candidates(rows)
    organic = [x for x in selected if x["role"] == "organic"]
    assert len(organic) == 5
    assert all("wikipedia.org" not in x["url"] and "fandom.com" not in x["url"] for x in organic)
    assert [x["role"] for x in selected[-2:]] == ["wikipedia", "fandom"]
    assert len(selected) == 7


def test_compile_facts_retains_disagreement_and_source_counts():
    sources = [
        {
            "url": "https://one.example",
            "_full_data": {
                "key_facts": [{"label": "Year", "value": "2013"}, {"label": "Status", "value": "Finished"}],
                "sections": {"resource_details": {"episodes": 25}},
            },
        },
        {
            "url": "https://two.example",
            "_full_data": {
                "key_facts": [{"label": "Year", "value": "2013"}, {"label": "Status", "value": "Completed"}],
                "sections": {"resource_details": {"episodes": 25}},
            },
        },
    ]
    compiled = sr.compile_facts(sources)
    year = next(x for x in compiled if x["label"] == "Year")
    episodes = next(x for x in compiled if x["label"] == "Episodes")
    status = next(x for x in compiled if x["label"] == "Status")
    assert year["values"][0]["value"] == "2013"
    assert year["values"][0]["source_count"] == 2
    assert episodes["values"][0]["source_count"] == 2
    assert {x["value"] for x in status["values"]} == {"Finished", "Completed"}


def test_search_bundle_uses_five_organic_and_supplemental_refs(monkeypatch):
    main = [
        _result("Wikipedia", "https://en.wikipedia.org/wiki/Attack_on_Titan", rank=1),
        _result("One", "https://one.example/a", rank=2),
        _result("Two", "https://two.example/a", rank=3),
        _result("Three", "https://three.example/a", rank=4),
        _result("Four", "https://four.example/a", rank=5),
        _result("Five", "https://five.example/a", rank=6),
    ]
    fandom = _result("Attack on Titan Wiki", "https://attackontitan.fandom.com/wiki/Attack_on_Titan_Wiki", rank=1)

    def fake_discover(query, preferred_engine=None, target_count=10):
        return main, [{"engine": "google", "query": query, "ok": True, "method": "camoufox", "rendered": True, "score": 0.8, "results_found": len(main)}]

    def fake_reference(query, kind, preferred_engine=None):
        if kind == "fandom":
            return fandom, [{"engine": "duckduckgo", "query": f"site:fandom.com {query}", "ok": True, "method": "httpx", "rendered": False, "score": 0.8, "results_found": 1}]
        raise AssertionError("Wikipedia was already present and should not require targeted discovery")

    def fake_analyze(url):
        return {
            "classification": {"kind": "anime_manga", "category": "Media / Anime & Manga"},
            "identity": {"title": "Attack on Titan"},
            "summary": "Humans fight for survival behind enormous walls.",
            "tags": ["anime", "action"],
            "key_facts": [{"label": "Year", "value": "2013"}],
            "sections": {"resource_details": {"status": "Finished"}},
            "quality": {"extraction_score": 0.9, "extraction_grade": "strong"},
        }

    monkeypatch.setattr(sr, "discover_results", fake_discover)
    monkeypatch.setattr(sr, "discover_reference", fake_reference)
    data = sr.analyze_search_input("Attack on Titan", fake_analyze)
    research = data["search_research"]

    assert data["classification"]["kind"] == "web_search_research"
    assert research["organic_selected"] == 5
    assert research["wikipedia_selected"] is True
    assert research["fandom_selected"] is True
    assert research["sources_selected"] == 7
    assert research["sources_succeeded"] == 7
    assert len([x for x in research["sources"] if x["role"] == "organic"]) == 5
    assert data["quality"]["extraction_grade"] == "strong"
    assert data["links"]["important"][-2]["relationship"] == "wikipedia"
    assert data["links"]["important"][-1]["relationship"] == "fandom"


def test_reference_absence_is_reported_not_replaced_with_wrong_domain(monkeypatch):
    main = [_result(str(i), f"https://site{i}.example/page", rank=i) for i in range(1, 7)]

    monkeypatch.setattr(
        sr,
        "discover_results",
        lambda query, preferred_engine=None, target_count=10: (
            main,
            [{"engine": "google", "query": query, "ok": True, "method": "httpx", "rendered": False, "score": 0.8, "results_found": 6}],
        ),
    )
    monkeypatch.setattr(sr, "discover_reference", lambda query, kind, preferred_engine=None: (None, []))

    def fake_analyze(url):
        return {
            "classification": {"kind": "general_webpage", "category": "Web / General"},
            "identity": {"title": url},
            "summary": "A source.",
            "tags": [],
            "key_facts": [],
            "sections": {},
            "quality": {"extraction_score": 0.6, "extraction_grade": "usable"},
        }

    data = sr.analyze_search_input("obscure thing", fake_analyze)
    research = data["search_research"]
    assert research["organic_selected"] == 5
    assert research["wikipedia_selected"] is False
    assert research["fandom_selected"] is False
    assert research["sources_selected"] == 5
    assert "Wikipedia supplemental reference" in data["quality"]["missing_or_uncertain"]
    assert "Fandom supplemental reference" in data["quality"]["missing_or_uncertain"]


def test_bing_redirect_unwrapping_decodes_base64_target():
    href = "/ck/a?!&&p=96a6d235e2cafdbdb3688f8911ebd8d6f232189086068914f2795f0bc61927faJmltdHM9MTc4ODQ4MDAwMA&ptn=3&ver=2&hsh=4&fclid=25650d1c-ae68-6399-2140-1ad7af726275&u=a1aHR0cHM6Ly9lbi53aWtpcGVkaWEub3JnL3dpa2kvQXR0YWNrX29uX1RpdGFu&ntb=1"
    unwrapped = sr._unwrap_search_href(href, "https://www.bing.com/search?q=Attack+on+Titan")
    assert unwrapped == "https://en.wikipedia.org/wiki/Attack_on_Titan"


def test_localhost_and_private_ip_bare_inputs_stay_url_mode():
    for raw in ("127.0.0.1", "127.0.0.1:8000", "localhost", "localhost:8080", "192.168.1.1", "10.0.0.1/admin"):
        target = sr.parse_input_target(raw)
        assert target.mode == "url", f"Expected {raw} to be treated as URL, got {target.mode}"
        assert target.url.startswith("https://")


def test_malformed_url_raises_search_research_error():
    import pytest
    for raw in ("http://", "https://", "http:///foo", "ftp://example.com", "file:///etc/passwd"):
        with pytest.raises(sr.SearchResearchError):
            sr.parse_input_target(raw)


def test_source_failure_does_not_abort_search_job(monkeypatch):
    main = [_result(f"Site {i}", f"https://site{i}.example", rank=i) for i in range(1, 6)]

    monkeypatch.setattr(sr, "discover_results", lambda q, p=None, target_count=10: (main, []))
    monkeypatch.setattr(sr, "discover_reference", lambda q, k, p=None: (None, []))

    def fake_analyze(url):
        if "site3" in url:
            raise RuntimeError("403 Forbidden")
        return {
            "classification": {"kind": "article", "category": "Reading / Article"},
            "identity": {"title": url},
            "summary": "OK summary.",
            "key_facts": [{"label": "Status", "value": "Active"}],
            "sections": {},
            "quality": {"extraction_score": 0.8, "extraction_grade": "usable"},
        }

    data = sr.analyze_search_input("test query", fake_analyze)
    research = data["search_research"]
    assert research["sources_selected"] == 5
    assert research["sources_succeeded"] == 4
    failed = next(s for s in research["sources"] if s["url"] == "https://site3.example")
    assert failed["status"] == "failed"
    assert "403 Forbidden" in failed["error"]
    assert len(research["compiled_facts"]) >= 1


def test_analyze_url_routes_search_engine_url_without_recursion(monkeypatch):
    import intel

    main = [_result("Site 1", "https://example.com/one", rank=1)]
    monkeypatch.setattr(sr, "discover_results", lambda q, p=None, target_count=10: (main, []))
    monkeypatch.setattr(sr, "discover_reference", lambda q, k, p=None: (None, []))

    def fake_concrete(url):
        return {
            "classification": {"kind": "article", "category": "Reading / Article"},
            "identity": {"title": "Example"},
            "summary": "Summary",
            "key_facts": [],
            "sections": {},
            "quality": {"extraction_score": 0.8, "extraction_grade": "usable"},
        }

    monkeypatch.setattr(intel, "_analyze_concrete_url", fake_concrete)
    res = intel.analyze_url("https://www.google.com/search?q=Attack%20on%20Titan")
    assert res["classification"]["kind"] == "web_search_research"
    assert res["identity"]["title"] == "Attack on Titan"

