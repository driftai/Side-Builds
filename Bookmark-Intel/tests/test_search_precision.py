from __future__ import annotations

from search_precision import finalize_search_precision


def _source(url, title, kind, summary, relevance, tags=None, role="organic", curation_role="source"):
    return {
        "url": url,
        "title": title,
        "role": role,
        "status": "ok",
        "subject_relevance_score": relevance,
        "subject_relevance_grade": "high" if relevance >= 0.7 else "medium",
        "curation_role": curation_role,
        "analysis": {
            "title": title,
            "kind": kind,
            "summary": summary,
            "quality_score": 0.8,
            "tags": tags or [],
        },
    }


def _bundle():
    crunchy = "https://www.crunchyroll.com/series/GY2P9ED0Y/code-geass"
    wiki = "https://en.wikipedia.org/wiki/Code_Geass"
    wikihow = "https://www.wikihow.com/Code-Geass-Watch-Order"
    netflix = "https://www.netflix.com/title/80065146"
    sources = [
        _source(
            crunchy,
            "Code Geass",
            "film_tv",
            "Lelouch receives the Geass power and rebels against Britannia.",
            0.85,
            ["anime", "action", "drama", "sci-fi", "thriller"],
            curation_role="watch_stream",
        ),
        _source(
            wikihow,
            "How to Watch Code Geass in Order: The Complete Guide",
            "article",
            "A guide to the Code Geass timelines.",
            0.76,
            ["anime", "article"],
            curation_role="watch_stream",
        ),
        _source(
            netflix,
            "Code Geass: Lelouch of the Rebellion",
            "film_tv",
            "These cookies, set by third parties, help us to customize and enhance your online experience with Netflix.",
            0.84,
            ["anime", "action", "full-length-movies", "instant-streaming", "watch-tv-online"],
            curation_role="watch_stream",
        ),
        _source(
            wiki,
            "Code Geass - Wikipedia",
            "article",
            'From Wikipedia, the free encyclopedia "Code Geass" redirects here.',
            0.70,
            ["anime", "manga", "article"],
            role="wikipedia",
            curation_role="reference",
        ),
    ]
    return {
        "input": {"query": "Code Geass"},
        "summary": "Lelouch receives the Geass power and rebels against Britannia.",
        "tags": [],
        "key_facts": [
            {"label": "Organic sources selected", "value": "5/5"},
            {"label": "Sources analyzed successfully", "value": "7/7"},
            {"label": "Wikipedia reference", "value": "selected"},
            {"label": "Fandom reference", "value": "selected"},
            {"label": "Inferred subject type", "value": "media"},
        ],
        "bookmark": {},
        "sections": {"search_research": {}},
        "links": {"important": []},
        "quality": {"semantic_curation_score": 0.90, "extraction_score": 0.90},
        "evidence_archive": {
            "links": [
                {"label": "Code Geass - Wikipedia", "url": wiki, "search_rank": 2, "selected_for_research": True},
                {"label": "Watch Code Geass - Crunchyroll", "url": crunchy, "search_rank": 5, "selected_for_research": True},
                {"label": "How to Watch Code Geass in Order: The Complete Guide", "url": wikihow, "search_rank": 7, "selected_for_research": True},
                {"label": "Watch Code Geass on Netflix", "url": netflix, "search_rank": 10, "selected_for_research": True},
                {"label": "Code Geass: Hangyaku no Lelouch - MyAnimeList", "url": "https://myanimelist.net/anime/1575/code_geass", "search_rank": 9, "selected_for_research": False},
                {"label": "Visual Studio Code - The open source AI code editor", "url": "https://code.visualstudio.com/", "search_rank": 12, "selected_for_research": False},
            ]
        },
        "search_research": {
            "query": "Code Geass",
            "sources": sources,
            "compiled_facts": [
                {"label": "Genres", "scope": "subject", "values": [{"value": "Action, Drama, Sci-Fi, Thriller", "source_count": 1, "sources": [crunchy]}]},
                {"label": "Score", "scope": "subject", "values": [{"value": "4.9", "source_count": 1, "sources": [wikihow]}]},
                {"label": "Volumes", "scope": "subject", "values": [{"value": "5", "source_count": 1, "sources": [wiki]}]},
                {"label": "Year", "scope": "subject", "values": [{"value": "2008", "source_count": 1, "sources": [wiki]}]},
                {"label": "Media Type", "scope": "subject", "values": [{"value": "TV Series", "source_count": 1, "sources": [crunchy]}]},
            ],
        },
    }


def test_partial_generic_query_match_does_not_promote_unrelated_code_result():
    data = finalize_search_precision(_bundle())
    urls = {row["url"] for row in data["links"]["important"]}
    assert "https://code.visualstudio.com/" not in urls
    assert "https://myanimelist.net/anime/1575/code_geass" in urls


def test_watch_order_guide_beats_generic_watch_role():
    data = finalize_search_precision(_bundle())
    guide = next(row for row in data["links"]["important"] if "wikihow.com" in row["url"])
    assert guide["curation_role"] == "guide"
    source = next(row for row in data["search_research"]["sources"] if "wikihow.com" in row["url"])
    assert source["curation_role"] == "guide"


def test_cookie_interstitial_source_is_quarantined_but_link_can_survive():
    data = finalize_search_precision(_bundle())
    netflix = next(row for row in data["search_research"]["sources"] if "netflix.com" in row["url"])
    assert netflix["subject_relevance_score"] <= 0.34
    assert netflix["subject_relevance_grade"] == "low"
    assert "Boilerplate" in netflix["curation_note"]
    assert any("netflix.com" in row["url"] for row in data["links"]["important"])


def test_streaming_seo_tags_do_not_pollute_parent():
    data = finalize_search_precision(_bundle())
    tags = set(data["tags"])
    assert {"anime", "action", "drama", "sci-fi", "thriller"} <= tags
    assert "full-length-movies" not in tags
    assert "instant-streaming" not in tags
    assert "watch-tv-online" not in tags


def test_ambiguous_single_source_score_year_and_volumes_are_removed():
    data = finalize_search_precision(_bundle())
    labels = {row["label"] for row in data["search_research"]["compiled_facts"]}
    assert "Score" not in labels
    assert "Volumes" not in labels
    assert "Year" not in labels
    assert "Genres" in labels
    assert "Media Type" in labels


def test_explicit_manga_query_allows_specialized_single_source_volume_count():
    data = _bundle()
    data["input"]["query"] = "One Piece manga"
    data["search_research"]["query"] = "One Piece manga"
    manga_url = "https://myanimelist.net/manga/13/One_Piece"
    data["search_research"]["sources"] = [
        _source(
            manga_url,
            "One Piece",
            "anime_manga",
            "One Piece is a manga series about Monkey D. Luffy.",
            0.9,
            ["manga", "adventure"],
            curation_role="database",
        )
    ]
    data["search_research"]["compiled_facts"] = [
        {"label": "Volumes", "scope": "subject", "values": [{"value": "112", "source_count": 1, "sources": [manga_url]}]}
    ]
    data["evidence_archive"]["links"] = [
        {"label": "One Piece manga - MyAnimeList", "url": manga_url, "search_rank": 1, "selected_for_research": True}
    ]
    out = finalize_search_precision(data)
    labels = {row["label"] for row in out["search_research"]["compiled_facts"]}
    assert "Volumes" in labels


def test_precision_score_preserves_previous_score_as_provenance():
    data = finalize_search_precision(_bundle())
    assert data["quality"]["pre_precision_semantic_score"] == 0.90
    assert data["quality"]["semantic_precision_score"] == data["quality"]["extraction_score"]
    assert data["quality"]["semantic_precision_score"] < 0.95


def test_non_search_data_is_unchanged():
    direct = {"classification": {"kind": "article"}, "identity": {"title": "Example"}}
    assert finalize_search_precision(direct) is direct
