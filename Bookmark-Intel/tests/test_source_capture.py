from types import SimpleNamespace

from provider_enrichment import ProviderEvidence
from source_capture import _mangadex_evidence, build_evidence_archive, finalize_analysis


MANGA_ID = "8bc61f6d-5b33-4c6b-bfdc-589daa4a4d78"


def test_mangadex_provider_recovers_full_series_metadata():
    info = {
        "data": {
            "id": MANGA_ID,
            "attributes": {
                "title": {"ja-ro": "Isekai wa Smartphone to Tomo ni"},
                "altTitles": [
                    {"en": "In Another World with My Smartphone"},
                    {"ja": "異世界はスマートフォンとともに。"},
                ],
                "description": {"en": "A smartphone-powered isekai adventure."},
                "status": "ongoing",
                "year": 2016,
                "publicationDemographic": "shounen",
                "contentRating": "safe",
                "originalLanguage": "ja",
                "lastVolume": "15",
                "lastChapter": "117",
                "availableTranslatedLanguages": ["en", "es"],
                "tags": [
                    {"attributes": {"name": {"en": "Action"}, "group": "genre"}},
                    {"attributes": {"name": {"en": "Magic"}, "group": "theme"}},
                    {"attributes": {"name": {"en": "Adaptation"}, "group": "format"}},
                ],
                "links": {"mal": "12345", "raw": "https://example.com/raw"},
            },
            "relationships": [
                {"type": "author", "attributes": {"name": "Fuyuhara Patora (冬原パトラ)"}},
                {"type": "artist", "attributes": {"name": "Soto"}},
                {"type": "cover_art", "attributes": {"fileName": "cover.jpg"}},
            ],
        }
    }
    stats = {
        "statistics": {
            MANGA_ID: {
                "rating": {"average": 7.4},
                "follows": 47000,
                "comments": {"repliesCount": 257},
            }
        }
    }

    def fake_fetch(url: str):
        return stats if "/statistics/" in url else info

    evidence = _mangadex_evidence(
        f"https://mangadex.org/title/{MANGA_ID}/isekai-wa-smartphone-to-tomo-ni",
        fake_fetch,
    )

    assert evidence.matched is True
    assert evidence.sufficient is True
    assert evidence.fields["title"] == "Isekai wa Smartphone to Tomo ni"
    assert "In Another World with My Smartphone" in evidence.fields["alternative_titles"]
    assert evidence.fields["authors"] == ["Fuyuhara Patora (冬原パトラ)"]
    assert evidence.fields["artists"] == ["Soto"]
    assert evidence.fields["genres"] == ["Action"]
    assert evidence.fields["themes"] == ["Magic"]
    assert evidence.fields["formats"] == ["Adaptation"]
    assert evidence.fields["status"] == "Ongoing"
    assert evidence.fields["year"] == "2016"
    assert evidence.fields["demographic"] == "Shounen"
    assert evidence.fields["final_chapter"] == "117"
    assert evidence.fields["score"] == "7.4"
    assert evidence.fields["media_type"] == "Manga"


def test_evidence_archive_keeps_unpromoted_links_and_label_values():
    html = """
    <html><body><main>
      <div><span>Demographic</span><span>Shounen</span></div>
      <div><span>Format</span><span>Adaptation</span></div>
      <div><span>Alternative Titles</span><span>In Another World with My Smartphone</span></div>
      <a href="https://bookwalker.jp/example">Book Walker</a>
      <a href="/titles?demos=shounen">Shounen</a>
    </main></body></html>
    """
    acquired = SimpleNamespace(
        text=html,
        content_type="text/html",
        final_url="https://mangadex.org/title/example",
    )
    data = {"links": {"important": []}}
    archive = build_evidence_archive(data, acquired)

    values = {(row["label"], row["value"]) for row in archive["labeled_facts"]}
    assert ("Demographic", "Shounen") in values
    assert ("Format", "Adaptation") in values
    assert ("Alternative Titles", "In Another World with My Smartphone") in values
    assert any(link["label"] == "Book Walker" for link in archive["links"])
    assert any(link["relationship"] == "internal" for link in archive["links"])


def test_finalize_repairs_manga_format_year_and_quality():
    html = """
    <html><body><main>
      <div><span>Publication</span><span>2016, Ongoing</span></div>
      <a href="https://bookwalker.jp/example">Book Walker</a>
    </main></body></html>
    """
    acquired = SimpleNamespace(
        text=html,
        content_type="text/html",
        final_url=f"https://mangadex.org/title/{MANGA_ID}/slug",
    )
    data = {
        "classification": {"kind": "anime_manga"},
        "identity": {"title": "Isekai wa Smartphone to Tomo ni - MangaDex"},
        "bookmark": {},
        "sections": {
            "resource_details": {"media_type": "Adaptation", "year": "2023-08-01"},
            "anime_manga": {"media_type": "Adaptation", "year": "2023-08-01"},
        },
        "key_facts": [{"label": "Author", "value": "Wrong Mixed Author, Soto"}],
        "entities": [
            {"type": "Person/Author", "name": "Fuyuhara Patora (冬原パトラ)"},
            {"type": "Author", "name": "Fuyuhara Patora (冬原パトラ)"},
        ],
        "tags": ["anime-manga"],
        "quality": {"extraction_score": 1.0, "missing_or_uncertain": ["status"]},
        "links": {"important": []},
    }
    provider = ProviderEvidence(
        adapter="mangadex",
        matched=True,
        sufficient=True,
        fields={
            "title": "Isekai wa Smartphone to Tomo ni",
            "description": "A smartphone-powered isekai adventure.",
            "authors": ["Fuyuhara Patora (冬原パトラ)"],
            "artists": ["Soto"],
            "genres": ["Action"],
            "themes": ["Magic"],
            "formats": ["Adaptation"],
            "status": "Ongoing",
            "year": "2016",
            "demographic": "Shounen",
            "media_type": "Manga",
            "final_chapter": "117",
        },
    )

    result = finalize_analysis(data, acquired, provider)
    media = result["sections"]["anime_manga"]

    assert result["identity"]["title"] == "Isekai wa Smartphone to Tomo ni"
    assert media["media_type"] == "Manga"
    assert media["formats"] == ["Adaptation"]
    assert media["year"] == "2016"
    assert media["status"] == "Ongoing"
    assert result["quality"]["extraction_score"] < 1.0
    assert "status" not in result["quality"]["missing_or_uncertain"]
    assert sum(1 for e in result["entities"] if e["name"] == "Fuyuhara Patora (冬原パトラ)") == 1
    author_fact = next(x for x in result["key_facts"] if x["label"] == "Author")
    assert author_fact["value"] == "Fuyuhara Patora (冬原パトラ)"
    assert result["evidence_archive"]["links"]


def test_mangadex_external_links_resolution_promotes_official_and_archives_all():
    acquired = SimpleNamespace(
        text="<html><body></body></html>",
        content_type="text/html",
        final_url=f"https://mangadex.org/title/{MANGA_ID}",
    )
    data = {"links": {"important": []}}
    provider = ProviderEvidence(
        adapter="mangadex",
        matched=True,
        sufficient=True,
        fields={
            "title": "Bleach",
            "external_ids": {
                "al": "30012",
                "bw": "series/13004/list",
                "mal": "12",
                "engtl": "https://mangaplus.shueisha.co.jp/titles/100004",
                "raw": "https://comic-walker.com/contents/detail/123",
            },
        },
    )
    archive = build_evidence_archive(data, acquired, provider)

    labels = {link["label"] for link in archive["links"]}
    assert "Book☆Walker" in labels
    assert "AniList" in labels
    assert "MyAnimeList" in labels
    assert "Official English" in labels
    assert "Official Raw" in labels

    # Check that Official English and Raw were promoted to important links
    important_labels = {link["label"] for link in data["links"]["important"]}
    assert "Official English" in important_labels
    assert "Official Raw" in important_labels

    bw_link = next(l for l in archive["links"] if l["label"] == "Book☆Walker")
    assert bw_link["url"] == "https://bookwalker.jp/series/13004/list"
    assert bw_link["region"] == "Read or Buy"

    mal_link = next(l for l in archive["links"] if l["label"] == "MyAnimeList")
    assert mal_link["url"] == "https://myanimelist.net/manga/12"
    assert mal_link["region"] == "Track"


def test_entity_dedupe_artist_and_parenthetical_variants():
    acquired = SimpleNamespace(
        text="<html><body></body></html>",
        content_type="text/html",
        final_url=f"https://mangadex.org/title/{MANGA_ID}",
    )
    data = {
        "classification": {"kind": "anime_manga"},
        "identity": {"title": "Series"},
        "entities": [
            {"type": "Publisher/Site", "name": "Atsumaru"},
            {"type": "Person/Author", "name": "Bihyen"},
            {"type": "Author", "name": "Araman"},
            {"type": "Author", "name": "Fuyuhara Patora"},
            {"type": "Author", "name": "Fuyuhara Patora (冬原パトラ)"},
            {"type": "Artist", "name": "Bihyen"},
        ],
        "sections": {"anime_manga": {}},
        "key_facts": [],
        "links": {"important": []},
        "quality": {},
    }
    provider = ProviderEvidence(
        adapter="atsu",
        matched=True,
        sufficient=True,
        fields={
            "title": "Series",
            "authors": ["Araman", "Fuyuhara Patora (冬原パトラ)"],
            "artists": ["Bihyen"],
            "chapter_count": 96,
            "chapter_record_count": 469,
            "latest_chapter": 96,
        },
    )

    result = finalize_analysis(data, acquired, provider)
    entities = result["entities"]

    # Person/Author Bihyen must be pruned because Bihyen is the Artist
    assert not any(e["type"].casefold() == "person/author" and e["name"] == "Bihyen" for e in entities)
    assert any(e["type"] == "Artist" and e["name"] == "Bihyen" for e in entities)

    # Shorter latin variant Fuyuhara Patora must be merged into parenthetical form
    author_patora_count = sum(1 for e in entities if "Fuyuhara Patora" in e["name"])
    assert author_patora_count == 1
    assert any(e["type"] == "Author" and e["name"] == "Fuyuhara Patora (冬原パトラ)" for e in entities)

    # Key facts check
    facts_dict = {f["label"]: f["value"] for f in result["key_facts"]}
    assert facts_dict["Artist"] == "Bihyen"
    assert facts_dict["Chapters"] == "96"
    assert facts_dict["Chapter records"] == "469"

