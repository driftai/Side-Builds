from types import SimpleNamespace

from bs4 import BeautifulSoup

from resource_coverage import (
    _clean_container_concatenations,
    _compact_item,
    _grouped_values,
    _merge_interactive_snapshots,
    _script_payloads,
    _structured_collections,
    _structured_script_groups,
    finalize_resource_coverage,
)


def _acquired(html: str, url: str = "https://example.test/info/6747/title"):
    return SimpleNamespace(
        text=html,
        content_type="text/html",
        final_url=url,
        score=0.87,
        rendered=False,
    )


def _base_data():
    return {
        "classification": {
            "kind": "film_tv",
            "category": "Media / Film & TV",
            "confidence": 0.98,
            "signals": ["TV schema.org type"],
            "alternatives": [],
        },
        "identity": {"title": "Dance in the Vampire Bund"},
        "summary": "A vampire queen establishes a colony in Japan.",
        "bookmark": {"suggested_folder": "Media / Film & TV"},
        "tags": ["film-tv", "video", "anime", "action"],
        "key_facts": [
            {"label": "Published", "value": "2010-01-07"},
            {"label": "Status", "value": "Finished"},
        ],
        "entities": [],
        "sections": {
            "resource_details": {
                "genres": ["Action", "Ecchi", "Romance", "Supernatural"],
                "status": "Finished",
                "score": "65",
                "media_type": "TV",
                "source_page_date": "2010-01-07",
                "country": "Japan",
                "runtime": "24 min",
                "studio": "Shaft",
            },
            "film_tv": {
                "media_type": "TV Series",
                "title": "Dance in the Vampire Bund",
                "status": "Finished",
                "country": "Japan",
                "runtime": "24 min",
                "studio": "Shaft",
            },
        },
        "quality": {
            "extraction_score": 0.57,
            "extraction_grade": "usable",
            "structured_fields_recovered": ["country", "genres", "status", "title"],
            "missing_or_uncertain": ["year", "genres"],
        },
        "evidence_archive": {
            "labeled_facts": [],
            "source_text_blocks": [],
            "links": [],
            "metadata": [],
            "capture_stats": {},
        },
    }


def test_hierarchical_media_facets_keep_anime_family_and_tv_format():
    html = """
    <html><body><main>
      <h1>Dance in the Vampire Bund</h1>
      <div>Anime Details and Episodes</div>
      <dl>
        <dt>Format</dt><dd>TV</dd>
        <dt>Status</dt><dd>Finished</dd>
        <dt>Episodes</dt><dd>12</dd>
        <dt>Season</dt><dd>Winter</dd>
        <dt>Start Date</dt><dd>January 7, 2010</dd>
        <dt>End Date</dt><dd>April 1, 2010</dd>
        <dt>Country</dt><dd>JP</dd>
        <dt>Adult</dt><dd>No</dd>
        <dt>Romaji</dt><dd>Dance in the Vampire Bund</dd>
        <dt>Native</dt><dd>ダンスインザヴァンパイアバンド</dd>
        <dt>Studios</dt>
        <dd>
          <a>Shaft</a><a>Genco</a><a>Funimation</a><a>Media Factory</a>
          <a>Rakuonsha</a><a>AT-X</a><a>flying DOG</a>
        </dd>
        <dt>Source</dt><dd>Manga</dd>
        <dt>Genres</dt><dd><a>Action</a><a>Ecchi</a><a>Romance</a><a>Supernatural</a></dd>
        <dt>Tags</dt><dd><a>Vampire</a><a>Urban Fantasy</a><a>Politics</a><a>Body Horror</a></dd>
      </dl>
      <a href="/search?type=ANIME">Anime</a>
    </main></body></html>
    """
    result = finalize_resource_coverage(_base_data(), _acquired(html), allow_interactive=False)

    assert result["classification"]["kind"] == "anime_manga"
    assert result["classification"]["category"] == "Media / Anime & Manga"
    assert result["classification"]["facets"]["media_family"] == "Anime"
    assert result["classification"]["facets"]["format"] == "TV"
    assert result["classification"]["facets"]["source_material"] == "Manga"

    anime = result["sections"]["anime_manga"]
    assert anime["media_type"] == "Anime"
    assert anime["format"] == "TV"
    assert anime["episodes"] == "12"
    assert anime["year"] == "2010"
    assert anime["start_date"] == "January 7, 2010"
    assert anime["end_date"] == "April 1, 2010"
    assert anime["studios"] == [
        "Shaft", "Genco", "Funimation", "Media Factory", "Rakuonsha", "AT-X", "flying DOG"
    ]
    assert anime["genres"] == ["Action", "Ecchi", "Romance", "Supernatural"]
    assert "Vampire" in anime["tags"]
    assert result["sections"]["resource_details"]["media_type"] == "Anime"
    assert "film_tv" not in result["sections"]
    assert "year" not in result["quality"]["missing_or_uncertain"]
    assert "genres" not in result["quality"]["missing_or_uncertain"]
    assert not any(x["label"] == "Published" and x["value"] == "2010-01-07" for x in result["key_facts"])


def test_unknown_grouped_values_survive_without_schema():
    html = """
    <html><body><main>
      <h3>Mystery Attributes</h3>
      <ul><li>Alpha</li><li>Beta</li><li>Gamma</li></ul>
    </main></body></html>
    """
    groups = _grouped_values(BeautifulSoup(html, "html.parser"))
    group = next(x for x in groups if x["label"] == "Mystery Attributes")
    assert group["values"] == ["Alpha", "Beta", "Gamma"]


def test_structured_collections_preserve_episode_array_without_promoting_every_item():
    html = """
    <html><body>
      <script type="application/json">
      {"page":{"episodes":[
        {"number":1,"title":"Prom Night","description":"Episode one","date":"2010-01-06"},
        {"number":2,"title":"Howling","description":"Episode two","date":"2010-01-13"},
        {"number":3,"title":"Teen Wolf","description":"Episode three","date":"2010-01-20"}
      ]}}
      </script>
    </body></html>
    """
    collections = _structured_collections(BeautifulSoup(html, "html.parser"))
    episodes = next(x for x in collections if x["path"].endswith(".episodes"))
    assert episodes["count"] == 3
    assert episodes["sample"][0]["title"] == "Prom Night"


def test_resource_coverage_detects_passive_same_resource_tabs_independent_of_html_health():
    html = """
    <html><body><main>
      <h1>Example Resource</h1>
      <p>A complete-looking overview page with lots of healthy server-rendered text.</p>
      <div role="tablist">
        <button role="tab">Overview</button>
        <button role="tab">Characters</button>
        <button role="tab">Artwork</button>
        <button role="tab">Episodes</button>
      </div>
    </main></body></html>
    """
    data = _base_data()
    data["summary"] = "A complete-looking overview page with lots of healthy server-rendered text."
    result = finalize_resource_coverage(data, _acquired(html), allow_interactive=False)
    coverage = result["resource_coverage"]

    assert coverage["html_health_score"] == 0.87
    assert coverage["resource_coverage_score"] < 1.0
    assert "Overview" in coverage["covered_sections"]
    assert {"Characters", "Artwork", "Episodes"} <= set(coverage["missing_sections"])
    assert coverage["needs_deepening"] is True


def test_embedded_episode_collection_can_satisfy_episode_tab_without_browser():
    html = """
    <html><body><main>
      <h1>Example Anime</h1>
      <p>Anime Details and Episodes</p>
      <button role="tab">Overview</button>
      <button role="tab">Episodes</button>
      <script type="application/json">
      {"resource":{"episodes":[
        {"number":1,"title":"One"},
        {"number":2,"title":"Two"}
      ]}}
      </script>
    </main></body></html>
    """
    result = finalize_resource_coverage(_base_data(), _acquired(html), allow_interactive=False)
    coverage = result["resource_coverage"]
    assert "Episodes" in coverage["covered_sections"]
    assert "Episodes" not in coverage["missing_sections"]


def test_interactive_snapshot_archive_keeps_new_text_groups_structured_data_and_links():
    base_html = "<html><body><main><h1>Show</h1><p>Overview text for the show.</p></main></body></html>"
    data = _base_data()
    acquired = _acquired(base_html)
    snapshot_html = """
    <html><body><main>
      <h2>Episodes</h2>
      <article><h3>EP 1 Prom Night</h3><p>Episode one summary.</p><time>Jan 06, 2010</time></article>
      <article><h3>EP 2 Howling</h3><p>Episode two summary.</p><time>Jan 13, 2010</time></article>
      <a href="/episode/1">Episode 1</a>
      <script type="application/json">
      {"episodes":[{"number":1,"title":"Prom Night"},{"number":2,"title":"Howling"}]}
      </script>
    </main></body></html>
    """
    snapshots = [{"label": "Episodes", "url": acquired.final_url, "html": snapshot_html}]
    _merge_interactive_snapshots(data, acquired, snapshots)
    archive = data["evidence_archive"]
    assert archive["interactive_sections"][0]["label"] == "Episodes"
    assert any("Prom Night" in x for x in archive["interactive_sections"][0]["text_blocks"])
    assert any(x["path"].endswith("episodes") for x in archive["structured_collections"])
    assert archive["interactive_sections"][0]["links"][0]["relationship"] == "internal"


def test_normal_article_is_not_reclassified_as_anime():
    html = """
    <html><body><main>
      <h1>How television animation changed over time</h1>
      <p>This long technical article discusses anime, TV series production, directors,
      seasons, and manga adaptations from a historical perspective.</p>
    </main></body></html>
    """
    data = {
        "classification": {"kind": "article", "category": "Reading / Article", "confidence": 0.99},
        "identity": {"title": "How television animation changed over time"},
        "summary": "A technical article.",
        "bookmark": {"suggested_folder": "Reading / Articles"},
        "tags": ["article"],
        "key_facts": [],
        "entities": [],
        "sections": {"editorial": {"word_count": 500}},
        "quality": {"extraction_score": 0.7, "missing_or_uncertain": []},
        "evidence_archive": {
            "labeled_facts": [],
            "source_text_blocks": [],
            "links": [],
            "metadata": [],
            "capture_stats": {},
        },
    }
    result = finalize_resource_coverage(data, _acquired(html, "https://example.test/blog/animation-history"), allow_interactive=False)
    assert result["classification"]["kind"] == "article"
    assert "editorial" in result["sections"]


def test_ssr_script_state_markers_and_payloads_extracted():
    html = """
    <html><head>
      <script>
        window.__SSR_DATA__ = {
          "title": {"romaji": "Dance in the Vampire Bund", "native": "ダンスインザヴァンパイアバンド"},
          "isAdult": false,
          "startDate": {"year": 2010, "month": 1, "day": 7},
          "endDate": {"year": 2010, "month": 4, "day": 1},
          "studios": {
            "edges": [
              {"node": {"name": "Shaft"}},
              {"node": {"name": "Genco"}},
              {"node": {"name": "Funimation"}}
            ]
          }
        };
      </script>
    </head><body><main><h1>Anime</h1></main></body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    payloads = _script_payloads(soup)
    assert len(payloads) >= 1
    assert payloads[0][0] == "__SSR_DATA__"
    assert "studios" in payloads[0][1]

    groups = _structured_script_groups(soup)
    studios_grp = next((g for g in groups if g["label"] == "Studios"), None)
    assert studios_grp is not None
    assert studios_grp["values"] == ["Shaft", "Genco", "Funimation"]

    adult_grp = next((g for g in groups if g["label"] == "Adult"), None)
    assert adult_grp is not None
    assert adult_grp["values"] == ["No"]

    romaji_grp = next((g for g in groups if g["label"] == "Romaji"), None)
    assert romaji_grp is not None
    assert romaji_grp["values"] == ["Dance in the Vampire Bund"]


def test_relay_graphql_compact_item_unwrapping():
    raw_character_edge = {
        "role": "MAIN",
        "node": {
            "name": {"userPreferred": "Mina Tepes", "full": "Mina Tepes"},
            "image": {"large": "https://example.test/mina.jpg"},
        },
        "voiceActors": [
            {
                "name": {"userPreferred": "Aoi Yuuki"},
                "language": "Japanese",
            },
            {
                "name": {"userPreferred": "Monica Rial"},
                "language": "English",
            },
        ],
    }
    compacted = _compact_item(raw_character_edge)
    assert compacted["name"] == "Mina Tepes"
    assert compacted["role"] == "MAIN"
    assert "Aoi Yuuki (Japanese)" in compacted["voiceActors"]
    assert "Monica Rial (English)" in compacted["voiceActors"]


def test_clean_container_concatenations_removes_composite_junk():
    raw_values = [
        "Action Ecchi Romance Supernatural",
        "Action",
        "Ecchi",
        "Romance",
        "Supernatural",
    ]
    cleaned = _clean_container_concatenations(raw_values)
    assert "Action Ecchi Romance Supernatural" not in cleaned
    assert cleaned == ["Action", "Ecchi", "Romance", "Supernatural"]

    # When no components match, distinct studio names are preserved
    studios = ["Shaft", "Media Factory", "flying DOG"]
    assert _clean_container_concatenations(studios) == studios


def test_interactive_snapshot_extracts_episodes_and_artwork():
    data = _base_data()
    acquired = _acquired("<html><body><main><h1>Show</h1></main></body></html>")
    episodes_html = """
    <html><body><main>
      <h2>Episodes</h2>
      <div>
        <button aria-label="EP 1: Prom Night">
          <span class="title">EP 1: Prom Night</span>
          <span class="airDate">Jan 06, 2010</span>
          <p class="description">Akira meets Mina.</p>
        </button>
        <button aria-label="EP 2: Howling">
          <span class="title">EP 2: Howling</span>
          <span class="airDate">Jan 13, 2010</span>
          <p class="description">Akira's memories return.</p>
        </button>
      </div>
    </main></body></html>
    """
    artwork_html = """
    <html><body><main>
      <h2>Artwork</h2>
      <div>
        <img src="https://example.test/banner.jpg" alt="Banner image" />
        <img src="https://example.test/cover.png" alt="Cover art" />
      </div>
    </main></body></html>
    """
    snapshots = [
        {"label": "Episodes", "url": acquired.final_url, "html": episodes_html},
        {"label": "Artwork", "url": acquired.final_url, "html": artwork_html},
    ]
    _merge_interactive_snapshots(data, acquired, snapshots)
    archive = data["evidence_archive"]
    collections = archive["structured_collections"]

    episodes_col = next(c for c in collections if c["path"] == "interactive.episodes")
    assert episodes_col["count"] == 2
    assert episodes_col["sample"][0]["number"] == 1
    assert episodes_col["sample"][0]["title"] == "Prom Night"
    assert episodes_col["sample"][0]["date"] == "Jan 06, 2010"

    artwork_col = next(c for c in collections if c["path"] == "interactive.artwork")
    assert artwork_col["count"] == 2
    assert artwork_col["sample"][0]["url"] == "https://example.test/banner.jpg"
    assert artwork_col["sample"][0]["label"] == "Banner image"


def test_visible_images_links_and_similar_in_html_prevent_unnecessary_deepening():
    html = """
    <html><body><main>
      <h1>Example Series</h1>
      <p>A full synopsis for this series is present here.</p>
      <div role="tablist">
        <button role="tab">Images</button>
        <button role="tab">Links</button>
        <button role="tab">Similar</button>
      </div>
      <img src="https://example.test/cover.jpg" alt="Series cover" />
      <h3>Links</h3>
      <a href="https://example.test/ch1">Chapter 1</a>
      <a href="https://example.test/ch2">Chapter 2</a>
      <h3>Similar series (beta)</h3>
      <p>Readers also like related fantasy titles.</p>
    </main></body></html>
    """
    data = _base_data()
    data["summary"] = "A full synopsis for this series is present here."
    result = finalize_resource_coverage(data, _acquired(html), allow_interactive=True)
    coverage = result["resource_coverage"]

    assert coverage["needs_deepening"] is False
    assert coverage["resource_coverage_score"] == 1.0
    assert coverage["missing_sections"] == []
    assert set(coverage["covered_sections"]) == {"Images", "Links", "Similar"}
    assert coverage.get("deepening_attempt") is None
    assert coverage.get("coverage_reconciled_from_visible_evidence") is True

