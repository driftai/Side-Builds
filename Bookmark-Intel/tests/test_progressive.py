from acquisition import AcquiredPage, AcquisitionAttempt, AcquisitionError, html_quality, validate_public_url
from enrichment import enrich_analysis
from intel_legacy import FetchResult, analyze_html


def acquired(html: str, url: str) -> AcquiredPage:
    score, _ = html_quality(html, url)
    return AcquiredPage(
        requested_url=url,
        final_url=url,
        redirects=[],
        status_code=200,
        content_type="text/html",
        text=html,
        byte_count=len(html.encode("utf-8")),
        method="camoufox",
        score=score,
        rendered=True,
        attempts=[AcquisitionAttempt(method="httpx", ok=True, score=0.1), AcquisitionAttempt(method="camoufox", ok=True, score=score)],
    )


def test_html_quality_detects_empty_spa_shell():
    html = '<html><head><script src="/a.js"></script><script src="/b.js"></script><script src="/c.js"></script><script src="/d.js"></script><script src="/e.js"></script></head><body><div id="__next"></div></body></html>'
    score, reasons = html_quality(html, "https://example.com/app")
    assert score < 0.58
    assert any("SPA shell" in reason or "script-heavy" in reason for reason in reasons)


def test_html_quality_accepts_rich_server_rendered_page():
    html = '<html><head><title>Useful Page</title><meta name="description" content="A useful description with enough information for extraction."></head><body><main><h1>Useful Page</h1><p>' + ('Detailed public content about the resource. ' * 40) + '</p></main></body></html>'
    score, _ = html_quality(html, "https://example.com/useful")
    assert score >= 0.7


def test_public_url_validation_rejects_loopback():
    try:
        validate_public_url("http://127.0.0.1:8000/private")
    except AcquisitionError:
        pass
    else:
        raise AssertionError("loopback URL was not rejected")


def test_rendered_spa_enrichment_recovers_specific_manga_information():
    url = "https://atsu.moe/manga/uUaKY"
    html = '''
    <html><head><title>Bleach</title><meta name="description" content="Ichigo Kurosaki gains the powers of a Soul Reaper and is drawn into battles involving spirits and the afterlife.">
      <script id="__NEXT_DATA__" type="application/json">{
        "props":{"pageProps":{"manga":{
          "title":"Bleach",
          "synopsis":"Ichigo Kurosaki gains the powers of a Soul Reaper and is drawn into battles involving spirits and the afterlife.",
          "authors":[{"name":"Tite Kubo"}],
          "genres":["Action","Supernatural","Adventure"],
          "status":"Finished",
          "chapters":686,
          "rating":8.7,
          "alternativeTitles":["BLEACH"]
        }}}
      }</script>
    </head><body><main><h1>Bleach</h1><div>Status</div><div>Finished</div><p>Ichigo Kurosaki gains Soul Reaper powers and protects people from dangerous spirits.</p></main></body></html>
    '''
    fetch = FetchResult(
        requested_url=url,
        final_url=url,
        redirects=[],
        status_code=200,
        content_type="text/html",
        text=html,
        byte_count=len(html.encode("utf-8")),
    )
    base = analyze_html(fetch)
    result = enrich_analysis(base, acquired(html, url))

    assert result["classification"]["kind"] == "anime_manga"
    assert result["identity"]["title"] == "Bleach"
    assert "Ichigo" in result["summary"]
    media = result["sections"]["anime_manga"]
    assert media["media_type"] == "Manga"
    assert media["status"] == "Finished"
    assert "Tite Kubo" in media["authors"]
    assert "Action" in media["genres"]
    assert str(media["chapters"]) == "686"
    assert any(entity["type"] == "Author" and entity["name"] == "Tite Kubo" for entity in result["entities"])
    assert "action" in result["tags"]
    assert result["quality"]["extraction_grade"] in {"usable", "strong"}
    assert result["acquisition"]["method"] == "camoufox"


def test_classification_confidence_and_extraction_quality_are_separate():
    url = "https://example.com/manga/abc"
    html = '<html><head></head><body><div id="__next"></div></body></html>'
    fetch = FetchResult(
        requested_url=url,
        final_url=url,
        redirects=[],
        status_code=200,
        content_type="text/html",
        text=html,
        byte_count=len(html),
    )
    base = analyze_html(fetch)
    result = enrich_analysis(base, acquired(html, url))
    assert result["classification"]["kind"] == "anime_manga"
    assert result["classification"]["confidence"] > result["quality"]["extraction_score"]
    assert result["quality"]["extraction_grade"] in {"minimal", "weak"}


def test_spa_state_mining_ignores_commenter_badges_and_recommendations():
    url = "https://example.com/item/1"
    html = '''
    <html><head><title>Actual Resource</title>
      <script id="__NEXT_DATA__" type="application/json">{
        "props":{"pageProps":{
          "title":"Actual Resource",
          "description":"The actual bookmarked resource synopsis.",
          "comments":[{"author":{"name":"User123"},"role":{"title":"Keyboard Warrior","description":"Earn reputation"}}],
          "recommendations":[{"title":"Unrelated Manga","description":"Something else"}],
          "mangaCommenters":[{"role":{"title":"Alpha"}}]
        }}
      }</script>
    </head><body><main><h1>Actual Resource</h1><p>The actual bookmarked resource synopsis.</p></main></body></html>
    '''
    fetch = FetchResult(
        requested_url=url,
        final_url=url,
        redirects=[],
        status_code=200,
        content_type="text/html",
        text=html,
        byte_count=len(html.encode("utf-8")),
    )
    base = analyze_html(fetch)
    result = enrich_analysis(base, acquired(html, url))
    assert result["identity"]["title"] == "Actual Resource"
    assert "actual bookmarked resource" in result["summary"].lower()
    assert not any("keyboard warrior" in str(e.get("name", "")).lower() for e in result["entities"])
    assert not any("alpha" in str(e.get("name", "")).lower() for e in result["entities"])

