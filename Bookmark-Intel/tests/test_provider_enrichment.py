from provider_enrichment import (
    ProviderEvidence,
    _atsu_evidence,
    _oembed_candidates,
    apply_provider_evidence,
    probe_provider,
)


def test_atsu_public_api_adapter_recovers_specific_resource_data():
    calls = []

    def fake_fetch(url):
        calls.append(url)
        if "/api/manga/page" in url:
            return {
                "mangaPage": {
                    "id": "uUaKY",
                    "title": "Bleach",
                    "englishTitle": "Bleach",
                    "otherNames": ["BLEACH"],
                    "description": "Ichigo Kurosaki gains the powers of a Soul Reaper.",
                    "authors": [{"name": "Tite Kubo"}],
                    "genres": ["Action", "Supernatural"],
                    "status": "Finished",
                    "type": "Manga",
                    "poster": {"smallImage": "bleach.webp"},
                }
            }
        return {
            "title": "Bleach",
            "chapters": [
                {"id": "a", "number": 1, "title": "Death & Strawberry", "scanId": "group-a"},
                {"id": "b", "number": 686, "title": "Death & Strawberry 2", "scanId": "group-a"},
            ],
        }

    evidence = _atsu_evidence("https://atsu.moe/manga/uUaKY", fake_fetch)

    assert evidence.matched is True
    assert evidence.sufficient is True
    assert evidence.fields["title"] == "Bleach"
    assert evidence.fields["authors"] == ["Tite Kubo"]
    assert "Action" in evidence.fields["genres"]
    assert evidence.fields["status"] == "Finished"
    assert evidence.fields["chapter_count"] == 2
    assert evidence.fields["latest_chapter"] == 686
    assert len(calls) == 2


def test_provider_evidence_upgrades_skeletal_manga_result():
    data = {
        "input": {"url": "https://atsu.moe/manga/uUaKY"},
        "identity": {"title": "https://atsu.moe/manga/uUaKY"},
        "classification": {"kind": "anime_manga", "confidence": 0.99},
        "summary": "No meaningful page summary could be extracted.",
        "sections": {"anime_manga": {"media_type": "Manga"}},
        "entities": [],
        "tags": ["anime-manga", "manga"],
        "bookmark": {"suggested_folder": "Media / Anime & Manga"},
        "key_facts": [],
        "quality": {
            "extraction_score": 0.14,
            "extraction_grade": "minimal",
            "missing_or_uncertain": ["description", "author"],
        },
    }
    evidence = ProviderEvidence(
        adapter="atsu",
        matched=True,
        sufficient=True,
        fields={
            "title": "Bleach",
            "description": "Ichigo Kurosaki gains the powers of a Soul Reaper.",
            "authors": ["Tite Kubo"],
            "genres": ["Action", "Supernatural"],
            "status": "Finished",
            "chapter_count": 686,
            "latest_chapter": 686,
            "media_type": "Manga",
            "provider_id": "uUaKY",
        },
        sources=["https://atsu.moe/api/manga/page?id=uUaKY"],
    )

    result = apply_provider_evidence(data, evidence)

    assert result["identity"]["title"] == "Bleach"
    assert "Ichigo" in result["summary"]
    assert result["sections"]["anime_manga"]["status"] == "Finished"
    assert result["sections"]["anime_manga"]["chapter_count"] == 686
    assert "Tite Kubo" in result["sections"]["anime_manga"]["authors"]
    assert any(e["type"] == "Author" and e["name"] == "Tite Kubo" for e in result["entities"])
    assert "action" in result["tags"]
    assert result["quality"]["extraction_score"] >= 0.62
    assert result["quality"]["extraction_grade"] in {"usable", "strong"}
    assert "description" not in result["quality"]["missing_or_uncertain"]
    assert result["provider_enrichment"]["adapter"] == "atsu"


def test_oembed_discovery_only_accepts_public_http_endpoints(monkeypatch):
    monkeypatch.setattr("provider_enrichment.validate_public_url", lambda url: url)
    html = """
    <html><head>
      <link rel="alternate" type="application/json+oembed" href="https://video.example/oembed?id=1">
      <link rel="alternate" type="application/json+oembed" href="javascript:alert(1)">
    </head></html>
    """
    assert _oembed_candidates(html, "https://video.example/watch/1") == [
        "https://video.example/oembed?id=1"
    ]


def test_non_atsu_url_does_not_match_atsu_adapter():
    evidence = _atsu_evidence("https://example.com/manga/uUaKY", lambda _: {})
    assert evidence.matched is False


def test_known_provider_probe_registry_can_return_none(monkeypatch):
    monkeypatch.setattr("provider_enrichment.validate_public_url", lambda url: url)
    assert probe_provider("https://example.com/article") is None


def test_atsu_extracts_artist_rating_year_and_poster_url():
    def fake_fetch(url):
        if "/api/manga/page" in url:
            return {
                "mangaPage": {
                    "id": "uUaKY",
                    "title": "Bleach",
                    "synopsis": "Soul Reaper adventures.",
                    "authors": [
                        {"name": "Tite Kubo", "type": "Author"},
                        {"name": "Tite Kubo", "type": "Artist"},
                    ],
                    "genres": [{"name": "Action"}, {"name": "Supernatural"}],
                    "status": "Completed",
                    "avgRating": 7.9188,
                    "released": 978307200000,
                    "poster": {"largeImage": "posters/bleach-large.avif"},
                }
            }
        return {
            "title": "Bleach",
            "chapters": [
                {"number": 1, "title": "Death & Strawberry"},
                {"number": 686.5, "title": "Chapter 686.5"},
            ],
        }

    evidence = _atsu_evidence("https://atsu.moe/manga/uUaKY", fake_fetch)
    assert evidence.fields["authors"] == ["Tite Kubo"]
    assert evidence.fields["artists"] == ["Tite Kubo"]
    assert evidence.fields["score"] == "7.92"
    assert evidence.fields["year"] == "2001"
    assert evidence.fields["poster"] == "https://atsu.moe/posters/bleach-large.avif"
    assert evidence.fields["chapter_count"] == 2
    assert evidence.fields["latest_chapter"] == 686.5


def test_authoritative_provider_authors_replaces_duplicate_meta_author():
    data = {
        "input": {"url": "https://atsu.moe/manga/uUaKY"},
        "identity": {"title": "https://atsu.moe/manga/uUaKY"},
        "classification": {"kind": "anime_manga", "confidence": 0.99},
        "summary": "No meaningful summary",
        "sections": {"anime_manga": {"authors": ["Tite Kubo, Tite Kubo"]}},
        "entities": [{"type": "Person/Author", "name": "Tite Kubo, Tite Kubo"}],
        "tags": ["anime-manga"],
        "key_facts": [],
        "quality": {},
    }
    evidence = ProviderEvidence(
        adapter="atsu",
        matched=True,
        sufficient=True,
        fields={
            "title": "Bleach",
            "authors": ["Tite Kubo"],
            "artists": ["Tite Kubo"],
        },
    )
    result = apply_provider_evidence(data, evidence)
    assert result["sections"]["anime_manga"]["authors"] == ["Tite Kubo"]
    assert result["sections"]["anime_manga"]["artists"] == ["Tite Kubo"]
    assert not any(e["name"] == "Tite Kubo, Tite Kubo" for e in result["entities"])
    assert any(e["type"] == "Author" and e["name"] == "Tite Kubo" for e in result["entities"])
    assert any(e["type"] == "Artist" and e["name"] == "Tite Kubo" for e in result["entities"])


def test_oembed_does_not_pollute_bookmark_tags():
    data = {
        "input": {"url": "https://video.example/watch/1"},
        "identity": {"title": "Sample Video"},
        "classification": {"kind": "video", "confidence": 0.9},
        "tags": ["video"],
        "sections": {},
        "entities": [],
        "key_facts": [],
        "quality": {},
    }
    evidence = ProviderEvidence(
        adapter="oembed",
        matched=True,
        sufficient=True,
        fields={"title": "Better Video Title", "provider_name": "SampleVideo"},
    )
    result = apply_provider_evidence(data, evidence)
    assert "oembed" not in result["tags"]


def test_atsu_chapter_semantics_total_vs_records():
    def fake_fetch(url):
        if "/api/manga/page" in url:
            return {
                "mangaPage": {
                    "id": "T7fIS",
                    "title": "Ultimate Shut-in",
                    "totalChapterCount": 96,
                }
            }
        return {
            "chapters": [
                {"id": "1", "number": 1, "title": "Episode 1", "scanId": "group-a"},
                {"id": "2", "number": 95, "title": "Chapter 95", "scanId": "group-b"},
                {"id": "3", "number": 96, "title": "Chapter 96", "scanId": "group-a"},
                {"id": "4", "number": 95, "title": "Chapter 95 (Duplicate Scan)", "scanId": "group-c"},
            ]
        }

    evidence = _atsu_evidence("https://atsu.moe/manga/T7fIS", fake_fetch)
    assert evidence.fields["chapter_count"] == 96
    assert evidence.fields["chapter_record_count"] == 4
    assert evidence.fields["latest_chapter"] == 96
    assert evidence.fields["latest_chapter_title"] == "Chapter 96"
    assert evidence.fields["scanlation_group_count"] == 3

