from types import SimpleNamespace

from universal_capture import universal_finalize


def _acquired(html: str, url: str = "https://example.test/watchseries/silo-online-free"):
    return SimpleNamespace(
        text=html,
        content_type="text/html",
        final_url=url,
    )


def test_generic_film_tv_reclassifies_article_and_promotes_source_facts():
    html = """
    <html>
      <head>
        <title>Silo Series Online Free Streaming - Watch HD TV Shows</title>
      </head>
      <body>
        <main>
          <h1>Silo</h1>
          <p>Men and women live in a giant silo underground with several regulations which they believe are in place to protect them from the toxic and ruined world on the surface.</p>
          <div>522 Votes(7.5)</div>
          <div>Year Started: 2023</div>
          <div>Certificate: TV-MA</div>
          <div>Country: United States</div>
          <div>Language: English</div>
          <div>Show Status: Returning Series</div>
          <div>Genre: Drama | Mystery |</div>
          <div>Keywords: #based on novel or book | #politics | #corruption | #silo |</div>
          <h2>Credits</h2>
          <a href="/person/4694">watch Rebecca Ferguson series online HD</a>
          <a href="/person/34395">watch Graham Yost series online HD</a>
          <div>Graham Yost director</div>
          <h2>Season 1</h2>
          <h2>Season 2</h2>
          <h2>Season 3</h2>
          <h2>Similar Series</h2>
          <a href="/watchseries/the-100-online-free">the 100</a>
          <a href="/watchseries/see-online-free">see</a>
          <div>13 comments</div>
        </main>
      </body>
    </html>
    """
    data = {
        "classification": {
            "kind": "article",
            "category": "Reading / Article",
            "confidence": 0.95,
            "signals": ["substantial long-form reading text"],
            "alternatives": [],
        },
        "identity": {"title": "Silo Series Online Free Streaming - Watch HD TV Shows"},
        "summary": "At Example you can watch Silo for absolutely free, No signup required, Just Click and watch right away.",
        "bookmark": {
            "suggested_folder": "Reading / Articles",
            "suggested_title": "Silo Series Online Free Streaming - Watch HD TV Shows",
            "suggested_tags": ["article", "drama"],
            "why_it_might_matter": "Structured reference.",
        },
        "sections": {
            "editorial": {"word_count": 380, "reading_time_minutes": 2},
            "resource_details": {"genres": ["Drama"]},
        },
        "tags": ["article", "drama"],
        "key_facts": [],
        "entities": [{"type": "Publisher/Site", "name": "Example"}],
        "links": {"important": []},
        "quality": {
            "extraction_score": 0.74,
            "extraction_grade": "usable",
            "structured_fields_recovered": ["genres"],
            "missing_or_uncertain": [],
        },
        "evidence_archive": {
            "labeled_facts": [],
            "links": [
                {
                    "label": "the 100",
                    "url": "https://example.test/watchseries/the-100-online-free",
                    "relationship": "internal",
                    "region": "body",
                }
            ],
            "metadata": [],
            "headings": [],
            "capture_stats": {"links_retained": 1},
        },
    }

    result = universal_finalize(data, _acquired(html))
    media = result["sections"]["film_tv"]

    assert result["classification"]["kind"] == "film_tv"
    assert result["classification"]["category"] == "Media / Film & TV"
    assert result["bookmark"]["suggested_folder"] == "Media / Film & TV"
    assert result["identity"]["title"] == "Silo"
    assert result["summary"].startswith("Men and women live in a giant silo")
    assert "editorial" not in result["sections"]

    assert media["media_type"] == "TV Series"
    assert media["year"] == "2023"
    assert media["status"] == "Returning Series"
    assert media["certificate"] == "TV-MA"
    assert media["country"] == "United States"
    assert media["language"] == "English"
    assert media["genres"] == ["Drama", "Mystery"]
    assert "based on novel or book" in media["keywords"]
    assert media["seasons"] == [1, 2, 3]
    assert media["season_count_visible"] == 3
    assert media["vote_count"] == 522
    assert media["score"] == "7.5"
    assert "Rebecca Ferguson" in media["people"]
    assert "Graham Yost" in media["directors"]
    assert "the 100" in media["similar_titles"]

    assert "article" not in result["tags"]
    assert "film-tv" in result["tags"]
    assert result["quality"]["extraction_grade"] == "strong"

    archive = result["evidence_archive"]
    assert any(f["label"] == "Year Started" and f["value"] == "2023" for f in archive["labeled_facts"])
    assert any("Men and women live in a giant silo" in block for block in archive["source_text_blocks"])
    similar_link = next(x for x in archive["links"] if x["label"] == "the 100")
    assert similar_link["relationship"] == "internal"
    assert similar_link["region"] == "body"
    assert similar_link["source_context"] == "Similar Series"


def test_unknown_label_is_preserved_even_without_a_curated_schema():
    html = """
    <html><body><main>
      <h1>Odd Resource</h1>
      <div>Weird Custom Metric: 42 Quux</div>
      <p>This is useful source information that the current schema does not understand yet.</p>
    </main></body></html>
    """
    data = {
        "classification": {"kind": "general_webpage", "category": "Web / General", "confidence": 0.7},
        "identity": {"title": "Odd Resource"},
        "bookmark": {},
        "sections": {},
        "tags": [],
        "key_facts": [],
        "entities": [],
        "links": {"important": []},
        "quality": {"extraction_score": 0.4},
        "evidence_archive": {"labeled_facts": [], "links": [], "metadata": [], "capture_stats": {}},
    }
    result = universal_finalize(data, _acquired(html, "https://example.test/odd"))

    assert result["classification"]["kind"] == "general_webpage"
    assert any(
        fact["label"] == "Weird Custom Metric" and fact["value"] == "42 Quux"
        for fact in result["evidence_archive"]["labeled_facts"]
    )
    assert any(
        "current schema does not understand yet" in block
        for block in result["evidence_archive"]["source_text_blocks"]
    )


def test_normal_article_is_not_reclassified_as_film_tv():
    html = """
    <html><head><title>Engineering Notes</title></head>
    <body><main>
      <h1>Engineering Notes</h1>
      <p>This article explains a long technical design decision and why it matters to maintainers.</p>
      <div>Author: Ada Example</div>
      <div>Published: 2026-09-05</div>
    </main></body></html>
    """
    data = {
        "classification": {"kind": "article", "category": "Reading / Article", "confidence": 0.9},
        "identity": {"title": "Engineering Notes"},
        "summary": "This article explains a long technical design decision and why it matters to maintainers.",
        "bookmark": {"suggested_folder": "Reading / Articles"},
        "sections": {"editorial": {"word_count": 200}},
        "tags": ["article"],
        "key_facts": [],
        "entities": [],
        "links": {"important": []},
        "quality": {"extraction_score": 0.7},
        "evidence_archive": {"labeled_facts": [], "links": [], "metadata": [], "capture_stats": {}},
    }

    result = universal_finalize(data, _acquired(html, "https://example.test/blog/engineering-notes"))
    assert result["classification"]["kind"] == "article"
    assert "editorial" in result["sections"]


def test_multi_sibling_labeled_facts_and_b_section_headers():
    html = """
    <html>
      <head><title>Test Show - Watch Free</title></head>
      <body>
        <main>
          <h1>Test Show</h1>
          <p>Synopsis of a fictional dystopian show in an underground facility.</p>
          <span>
            <b>Genre:</b> <a href="/genre/drama">Drama</a> | <a href="/genre/mystery">Mystery</a> |
            <b>Show Status:</b> Returning Series
            <b>Year Started:</b> 2023
          </span>
          <div class="credits-box">
            <b>Credits:</b>
            <a href="/person/101" title="watch Jane Doe series">Jane Doe</a>
          </div>
          <div>Season 1</div>
          <div class="similar-box">
            <b class="smhead" name="similar-movies">Similar Series</b>
            <div>
              <a class="poster" href="/watchseries/the-100-online-free" title="the 100"></a>
              <a href="/watchseries/the-100-online-free">The 100</a>
              <a href="/watchseries/see-online-free">See</a>
            </div>
          </div>
        </main>
        <footer>
          <a href="/faq">FAQ</a>
          <a href="/terms-of-service">Terms of Service</a>
        </footer>
      </body>
    </html>
    """
    data = {
        "classification": {"kind": "article", "category": "Reading / Article", "confidence": 0.8},
        "identity": {"title": "Test Show - Watch Free"},
        "summary": "Watch Test Show for free online streaming.",
        "bookmark": {},
        "sections": {},
        "tags": ["article"],
        "key_facts": [],
        "entities": [],
        "links": {"important": []},
        "quality": {"extraction_score": 0.6},
        "evidence_archive": {
            "labeled_facts": [],
            "links": [
                {"label": "The 100", "url": "https://example.test/watchseries/the-100-online-free", "relationship": "internal", "region": "body"},
                {"label": "Jane Doe", "url": "https://example.test/person/101", "relationship": "internal", "region": "body"},
                {"label": "FAQ", "url": "https://example.test/faq", "relationship": "internal", "region": "body"},
            ],
            "metadata": [],
            "capture_stats": {},
        },
    }
    result = universal_finalize(data, _acquired(html, "https://example.test/watchseries/test-show-online-free"))
    media = result["sections"]["film_tv"]

    assert result["classification"]["kind"] == "film_tv"
    assert media["genres"] == ["Drama", "Mystery"]
    assert "The 100" in media["similar_titles"]
    assert "See" in media["similar_titles"]
    assert "FAQ" not in media["similar_titles"]
    assert "Terms of Service" not in media["similar_titles"]

    archive = result["evidence_archive"]
    the_100_link = next(x for x in archive["links"] if x["label"] == "The 100")
    assert the_100_link.get("source_context") == "Similar Series"
    jane_link = next(x for x in archive["links"] if x["label"] == "Jane Doe")
    assert jane_link.get("source_context") == "Credits"
    faq_link = next(x for x in archive["links"] if x["label"] == "FAQ")
    assert "source_context" not in faq_link or faq_link.get("source_context") is None

