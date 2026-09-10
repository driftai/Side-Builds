from types import SimpleNamespace

from comic_resource import finalize_comic_resource


def _acquired(html: str, url: str = "https://example.test/oel/596726/shadow-slave"):
    return SimpleNamespace(text=html, content_type="text/html", final_url=url)


def _base_data():
    return {
        "classification": {"kind": "article", "category": "Reading / Article", "confidence": 0.83, "signals": ["article schema.org type"], "alternatives": []},
        "identity": {"title": "Shadow Slave | Action Adventure Oel | ExampleDB"},
        "summary": "Growing up in poverty, Sunny never expected anything good from life. However, even he did not anticipate being chosen by the Nightmare…",
        "bookmark": {"suggested_folder": "Reading / Tech Essays & Blogs"},
        "tags": ["article", "programming", "anime", "fantasy", "action"],
        "key_facts": [
            {"label": "Author", "value": "@ExampleDBOrg"},
            {"label": "Published", "value": "2026-07-15"},
            {"label": "Modified", "value": "2026-09-04T22:46:53.383Z"},
            {"label": "Genre", "value": "['Fantasy', 'Action']"},
        ],
        "entities": [
            {"type": "ComicSeries", "name": "Shadow Slave"},
            {"type": "Publisher/Site", "name": "ExampleDB"},
            {"type": "Social/Creator", "name": "@ExampleDBOrg"},
            {"type": "Author", "name": "@ExampleDBOrg"},
        ],
        "sections": {
            "editorial": {"author": "@ExampleDBOrg", "word_count": 171},
            "resource_details": {"authors": "@ExampleDBOrg", "source_page_date": "2026-07-15"},
        },
        "quality": {"extraction_score": 0.95, "structured_fields_recovered": ["authors", "genres", "year"], "missing_or_uncertain": []},
        "evidence_archive": {
            "grouped_values": [
                {"label": "Meta", "values": ["oel", "releasing", "Licensed", "7", "2026", "#3"]},
                {"label": "Similar series (beta)", "values": ["Based on shared tags"]},
            ],
            "source_text_blocks": ["Similar series (beta)", "Based on shared tags"],
            "structured_collections": [],
            "links": [{"label": "Publisher", "url": "https://publisher.example"}, {"label": "Other", "url": "https://other.example"}],
            "metadata": [],
            "capture_stats": {},
        },
        "resource_coverage": {
            "html_health_score": 0.96,
            "resource_coverage_score": 0.0,
            "interactive_sections_detected": [{"label": "Images"}, {"label": "Links"}, {"label": "Similar"}],
            "covered_sections": [],
            "missing_sections": ["Images", "Links", "Similar"],
            "needs_deepening": True,
        },
    }


def _comic_html(author_json=""):
    description = (
        "Growing up in poverty, Sunny never expected anything good from life. However, even he did not anticipate "
        "being chosen by the Nightmare Spell and becoming one of the Awakened — an elite group gifted with supernatural powers. "
        "Transported into a ruined magical world, he faces terrible monsters in a deadly battle of survival. "
        "Born a slave. Destined for the grave. He chooses to survive. No matter the cost…"
    )
    author_field = f',"author":{{"@type":"Person","name":"{author_json}"}}' if author_json else ""
    return f'''<html><head><title>Shadow Slave | Action Adventure Oel | ExampleDB</title>
    <script type="application/ld+json">{{"@type":"ComicSeries","name":"Shadow Slave","description":"{description}","datePublished":"2026-07-15","dateModified":"2026-09-04T22:46:53.383Z","alternateName":["Escravo Das Sombras","Шадоу Слейв","シャドウスレイブ"],"genre":["Fantasy","Sci-Fi","Supernatural","Action","Adventure"],"keywords":["Psychological","Tragedy"]{author_field}}}</script>
    </head><body><main><h1>Shadow Slave</h1><h2>Meta</h2><div>oel releasing Licensed 7 Ch. 2026 #3</div>
    <h2>Description</h2><p>{description}</p><h2>Links</h2><div><span>Publisher</span><a href="https://publisher.example">Aethon Webcomics</a></div>
    <a href="https://other.example">External link</a><h2>Similar series (beta)</h2><p>Based on shared tags</p>
    <img src="https://cdn.example/cover.jpg" alt="Cover image for Shadow Slave"></main></body></html>'''


def test_comic_series_schema_overrides_generic_article_and_promotes_series_fields():
    result = finalize_comic_resource(_base_data(), _acquired(_comic_html()))
    assert result["classification"]["kind"] == "anime_manga"
    assert result["classification"]["category"] == "Media / Anime & Manga"
    assert result["classification"]["facets"] == {"media_family": "Comics", "format": "OEL", "source_material": None}
    assert result["identity"]["title"] == "Shadow Slave"
    assert result["sections"]["anime_manga"]["media_type"] == "Comic"
    assert result["sections"]["anime_manga"]["chapters"] == 7
    assert result["sections"]["anime_manga"]["status"] == "Releasing"
    assert result["sections"]["anime_manga"]["licensed"] == "Yes"
    assert result["sections"]["anime_manga"]["publisher"] == "Aethon Webcomics"
    assert result["sections"]["anime_manga"]["rank"] == "#3"
    assert "editorial" not in result["sections"]
    assert result["bookmark"]["suggested_folder"] == "Media / Anime & Manga"


def test_full_structured_description_beats_truncated_metadata_summary_and_dates_are_resource_semantics():
    result = finalize_comic_resource(_base_data(), _acquired(_comic_html()))
    assert result["summary"].endswith("No matter the cost…")
    facts = {row["label"]: row["value"] for row in result["key_facts"]}
    assert facts["Start date"] == "2026-07-15"
    assert facts["Last update"] == "2026-09-04T22:46:53.383Z"
    assert "Published" not in facts
    assert "Modified" not in facts
    assert facts["Chapters"] == "7"
    assert facts["Year"] == "2026"
    assert facts["Licensed"] == "Yes"
    assert "Genre" not in facts
    assert "Genres" in facts


def test_site_social_handle_is_not_promoted_as_work_author_but_real_series_author_is_preserved():
    without_creator = finalize_comic_resource(_base_data(), _acquired(_comic_html()))
    assert "authors" not in without_creator["sections"]["resource_details"]
    assert not any(row.get("label") == "Author" for row in without_creator["key_facts"])
    assert not any("author" in str(e.get("type", "")).casefold() for e in without_creator["entities"] if isinstance(e, dict))

    with_creator = finalize_comic_resource(_base_data(), _acquired(_comic_html("Guiltythree")))
    assert with_creator["sections"]["anime_manga"]["authors"] == ["Guiltythree"]
    assert with_creator["sections"]["resource_details"]["authors"] == ["Guiltythree"]


def test_visible_images_links_and_similar_content_reconcile_false_zero_coverage():
    result = finalize_comic_resource(_base_data(), _acquired(_comic_html()))
    coverage = result["resource_coverage"]
    assert coverage["resource_coverage_score"] == 1.0
    assert coverage["needs_deepening"] is False
    assert coverage["missing_sections"] == []
    assert set(coverage["covered_sections"]) == {"Images", "Links", "Similar"}
    assert coverage["coverage_reconciled_from_visible_evidence"] is True


def test_normal_article_that_mentions_comics_is_not_promoted():
    data = _base_data()
    data["entities"] = []
    data["evidence_archive"]["grouped_values"] = []
    html = '''<html><body><main><h1>How comics changed</h1><p>This article discusses manga, webtoons, comic series, chapters and releasing schedules historically.</p></main></body></html>'''
    result = finalize_comic_resource(data, _acquired(html, "https://example.test/blog/comics-history"))
    assert result["classification"]["kind"] == "article"
    assert "editorial" in result["sections"]
