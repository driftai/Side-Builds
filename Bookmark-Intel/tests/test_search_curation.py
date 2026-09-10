from __future__ import annotations

from search_curation import finalize_search_research


def _source(url, title, kind, summary, quality, tags=None, role="organic", status="ok"):
    return {
        "url": url,
        "title": title,
        "role": role,
        "status": status,
        "analysis": {
            "title": title,
            "kind": kind,
            "summary": summary,
            "quality_score": quality,
            "tags": tags or [],
            "key_facts": [],
        },
    }


def _base_bundle():
    sources = [
        _source(
            "http://www.geass.jp/",
            "コードギアスシリーズ公式サイト",
            "article",
            "Latest franchise announcements and merchandise updates.",
            0.74,
            ["anime", "article"],
        ),
        _source(
            "https://www.crunchyroll.com/series/GY2P9ED0Y/code-geass",
            "Code Geass",
            "film_tv",
            "Lelouch Lamperouge receives the Geass power from C.C. and leads a rebellion against the Holy Britannian Empire.",
            0.44,
            ["anime", "action", "film-tv"],
        ),
        _source(
            "https://www.imdb.com/title/tt0994314/",
            "JavaScript is disabled",
            "general_webpage",
            "No meaningful page summary could be extracted.",
            0.29,
            ["javascript", "general-webpage"],
        ),
        _source(
            "https://www.wikihow.com/Code-Geass-Watch-Order",
            "How to Watch Code Geass in Order: The Complete Guide",
            "article",
            "Code Geass follows an exiled prince waging a rebellion with the power of absolute obedience.",
            0.93,
            ["anime", "article"],
        ),
        _source(
            "https://en.wikipedia.org/wiki/Code_Geass",
            "Code Geass - Wikipedia",
            "article",
            'From Wikipedia, the free encyclopedia "Code Geass: Lelouch of the Rebellion" redirects here.',
            0.98,
            ["anime", "manga", "article"],
            role="wikipedia",
        ),
        _source(
            "https://codegeass.fandom.com/wiki/Code_Geass_Wiki",
            "Code Geass Wiki",
            "article",
            "The wiki that anyone can edit, devoted to Code Geass. Happy editing!",
            0.78,
            ["anime", "security", "article"],
            role="fandom",
        ),
    ]
    return {
        "input": {"raw": "Code Geass", "mode": "search", "query": "Code Geass"},
        "classification": {"kind": "web_search_research", "category": "Research / Web Search", "confidence": 0.99},
        "identity": {"title": "Code Geass"},
        "summary": 'From Wikipedia, the free encyclopedia "Code Geass" redirects here.',
        "tags": ["web-search", "research", "article", "javascript", "security"],
        "key_facts": [
            {"label": "Organic sources selected", "value": "4/5"},
            {"label": "Sources analyzed successfully", "value": "6/6"},
            {"label": "Wikipedia reference", "value": "selected"},
            {"label": "Fandom reference", "value": "selected"},
            {"label": "Dominant source type", "value": "article"},
        ],
        "sections": {"search_research": {}},
        "links": {"important": []},
        "bookmark": {"suggested_tags": []},
        "evidence_archive": {
            "links": [
                {"label": "コードギアスシリーズ公式サイト", "url": "http://www.geass.jp/", "search_rank": 1, "selected_for_research": True},
                {"label": "Code Geass", "url": "https://www.crunchyroll.com/series/GY2P9ED0Y/code-geass", "search_rank": 2, "selected_for_research": True},
                {"label": "Code Geass IMDb", "url": "https://www.imdb.com/title/tt0994314/", "search_rank": 3, "selected_for_research": True},
                {"label": "How to Watch Code Geass in Order", "url": "https://www.wikihow.com/Code-Geass-Watch-Order", "search_rank": 4, "selected_for_research": True},
                {"label": "Code Geass - Wikipedia", "url": "https://en.wikipedia.org/wiki/Code_Geass", "search_rank": 6, "selected_for_research": True},
                {"label": "Code Geass Wiki", "url": "https://codegeass.fandom.com/wiki/Code_Geass_Wiki", "search_rank": 7, "selected_for_research": True},
                {"label": "Code Geass on MyAnimeList", "url": "https://myanimelist.net/anime/1575/Code_Geass", "search_rank": 8, "selected_for_research": False},
            ]
        },
        "quality": {"extraction_score": 0.95, "extraction_grade": "strong", "structured_fields_recovered": ["search_sources", "compiled_facts"]},
        "search_research": {
            "query": "Code Geass",
            "sources": sources,
            "compiled_tags": ["anime", "article", "javascript", "security", "film-tv", "manga"],
            "compiled_facts": [
                {"label": "Author", "values": [{"value": "Contributors to Wikimedia projects", "source_count": 1, "sources": ["https://en.wikipedia.org/wiki/Code_Geass"]}]},
                {"label": "Published", "values": [{"value": "2006-09-10T19:03:36Z", "source_count": 1, "sources": ["https://en.wikipedia.org/wiki/Code_Geass"]}]},
                {"label": "Reading Time Minutes", "values": [{"value": "8", "source_count": 1, "sources": ["https://en.wikipedia.org/wiki/Code_Geass"]}]},
                {"label": "Genres", "values": [{"value": "Alternate history, Mecha, Military fiction", "source_count": 1, "sources": ["https://en.wikipedia.org/wiki/Code_Geass"]}]},
                {"label": "Year", "values": [{"value": "April 1, 2008", "source_count": 1, "sources": ["https://en.wikipedia.org/wiki/Code_Geass"]}]},
                {"label": "Score", "values": [{"value": "4.9", "source_count": 1, "sources": ["https://www.wikihow.com/Code-Geass-Watch-Order"]}]},
            ],
        },
    }


def test_source_page_metadata_is_removed_from_subject_facts():
    data = finalize_search_research(_base_bundle())
    labels = {row["label"] for row in data["search_research"]["compiled_facts"]}
    assert "Author" not in labels
    assert "Published" not in labels
    assert "Reading Time Minutes" not in labels
    assert "Genres" in labels


def test_boilerplate_wikipedia_summary_is_replaced_by_subject_overview():
    data = finalize_search_research(_base_bundle())
    assert "Lelouch Lamperouge" in data["summary"]
    assert "From Wikipedia" not in data["summary"]
    assert data["search_research"]["overview_source"].startswith("https://www.crunchyroll.com/")


def test_weak_page_tags_do_not_pollute_parent_tags():
    data = finalize_search_research(_base_bundle())
    tags = set(data["tags"])
    assert "article" not in tags
    assert "general-webpage" not in tags
    assert "javascript" not in tags
    assert "anime" in tags


def test_year_field_is_normalized_away_from_page_date_shape():
    data = finalize_search_research(_base_bundle())
    year = next(row for row in data["search_research"]["compiled_facts"] if row["label"] == "Year")
    assert year["values"][0]["value"] == "2008"


def test_curated_links_use_discovered_results_and_assign_roles():
    data = finalize_search_research(_base_bundle())
    links = data["links"]["important"]
    roles = {row["curation_role"] for row in links}
    assert "official" in roles
    assert "watch_stream" in roles
    assert "database" in roles
    assert "reference" in roles
    assert any("MyAnimeList" in row["label"] for row in links)
    assert all(row.get("reason") for row in links)


def test_single_source_article_score_is_not_promoted_as_subject_rating():
    data = finalize_search_research(_base_bundle())
    labels = {row["label"] for row in data["search_research"]["compiled_facts"]}
    assert "Score" not in labels


def test_quality_reflects_semantic_curation_not_only_source_success():
    data = finalize_search_research(_base_bundle())
    assert data["quality"]["pipeline_execution_score"] == 0.95
    assert 0.5 <= data["quality"]["semantic_curation_score"] <= 0.95
    assert data["quality"]["quality_basis"].startswith("search source coverage")


def test_subject_type_is_inferred_from_specialized_media_evidence():
    data = finalize_search_research(_base_bundle())
    assert data["search_research"]["subject_type"] == "media"
    assert any(row["label"] == "Inferred subject type" for row in data["key_facts"])


def test_legitimate_subject_author_from_specialized_source_is_preserved():
    bundle = _base_bundle()
    bundle["search_research"]["compiled_facts"].append(
        {
            "label": "Author",
            "values": [
                {
                    "value": "Sunrise",
                    "source_count": 1,
                    "sources": ["https://www.crunchyroll.com/series/GY2P9ED0Y/code-geass"],
                }
            ],
        }
    )
    data = finalize_search_research(bundle)
    facts = {row["label"]: row["values"][0]["value"] for row in data["search_research"]["compiled_facts"]}
    assert "Author" in facts
    assert facts["Author"] == "Sunrise"

