from link_semantics import normalize_link_semantics


def test_generic_pages_do_not_inherit_media_or_manga_link_roles():
    data = {
        "input": {"url": "https://example.test/watchseries/silo"},
        "links": {
            "important": [
                {"label": "Some external page", "url": "https://elsewhere.test/x", "relationship": "read_or_buy"}
            ]
        },
        "evidence_archive": {
            "links": [
                {
                    "label": "Trailer",
                    "url": "https://elsewhere.test/trailer",
                    "relationship": "external",
                    "region": "Read or Buy",
                    "source_context": "Credits",
                },
                {
                    "label": "Related",
                    "url": "https://example.test/related",
                    "relationship": "track",
                    "region": "Track",
                },
            ]
        },
    }
    result = normalize_link_semantics(data)
    assert result["link_semantics"]["mode"] == "neutral_generic"
    assert result["evidence_archive"]["links"][0]["region"] == "body"
    assert result["evidence_archive"]["links"][0]["relationship"] == "external"
    assert result["evidence_archive"]["links"][0]["source_context"] == "Credits"
    assert result["evidence_archive"]["links"][1]["region"] == "body"
    assert result["evidence_archive"]["links"][1]["relationship"] == "internal"
    assert result["links"]["important"][0]["relationship"] == "external"


def test_mangadex_provider_keeps_explicit_link_roles():
    data = {
        "provider_enrichment": {"adapter": "mangadex", "matched": True, "sufficient": True},
        "input": {"url": "https://mangadex.org/title/example"},
        "links": {
            "important": [
                {"label": "Official English", "url": "https://publisher.test/title", "relationship": "read_or_buy"}
            ]
        },
        "evidence_archive": {
            "links": [
                {
                    "label": "Book Walker",
                    "url": "https://bookwalker.jp/title",
                    "relationship": "external",
                    "region": "Read or Buy",
                }
            ]
        },
    }
    result = normalize_link_semantics(data)
    assert result["link_semantics"]["mode"] == "provider_explicit"
    assert result["evidence_archive"]["links"][0]["region"] == "Read or Buy"
    assert result["links"]["important"][0]["relationship"] == "read_or_buy"
