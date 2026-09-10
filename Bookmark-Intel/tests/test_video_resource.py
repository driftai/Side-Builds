from __future__ import annotations

from types import SimpleNamespace

from video_resource import finalize_video_resource


HTML = r'''
<html><head>
<meta name="description" content="Short description…">
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "VideoObject",
  "name": "Cyberpunk: Edgerunners | I Really Want to Stay At Your House | Music Video",
  "description": "Thank you to all of the incredible artists who contributed to the magic that is Cyberpunk: Edgerunners, and to all of the fans who blew the show up to create one of the most memorable anime of Netflix history to date.",
  "uploadDate": "2022-10-03T11:00:00-07:00",
  "duration": "PT263S",
  "interactionStatistic": [
    {"@type":"InteractionCounter","interactionType":{"@type":"WatchAction"},"userInteractionCount":"89115913"}
  ]
}
</script>
</head><body>
<main>
<h1>Cyberpunk: Edgerunners | I Really Want to Stay At Your House | Music Video</h1>
<div>Netflix 33.6M subscribers</div>
<div>1.2M Share</div>
<div>89,115,913 views • Oct 3, 2022</div>
<div>42,998 Comments</div>
<div>0:00 / 4:22</div>
<div>Thank you to all of the incredible artists who contributed to the magic that is Cyberpunk: Edgerunners.</div>
<a href="https://www.youtube.com/channel/UCNETFLIX">Netflix</a>
<a href="https://www.youtube.com/redirect?event=video_description&q=https%3A%2F%2Flnk.to%2Firwtsayh">https://lnk.to/irwtsayh</a>
<a href="https://www.youtube.com/redirect?event=Watch_SD_EP&q=https%3A%2F%2Fwww.instagram.com%2Fnetflix%2F">Instagram</a>
<a href="https://www.youtube.com/watch?v=BnnbP7pCIvQ">Cyberpunk: Edgerunners — Ending Theme | Let You Down</a>
<a href="https://www.youtube.com/watch?v=09K79_bD6w0">The silence of the night Japanese Lo-fi Study Focus</a>
<a href="https://www.youtube.com/watch?v=2AnDnFtHtng">David Martinez's Lie: What the Game Never Tells You</a>
<div>42,998 Comments</div>
<script>var x={"authorText":{"simpleText":"@stu92186"}};</script>
</main>
</body></html>
'''


def _data():
    return {
        "input": {"url": "https://www.youtube.com/watch?v=KvMY1uzSC1E"},
        "fetch": {"final_url": "https://www.youtube.com/watch?v=KvMY1uzSC1E"},
        "classification": {"kind": "video", "category": "Media / Video", "confidence": 0.99},
        "identity": {"title": "Cyberpunk: Edgerunners | I Really Want to Stay At Your House | Music Video"},
        "summary": "Thank you to all of the incredible artists who contributed to the magic that is Cyberpunk: Edgerunners…",
        "tags": ["video", "cyberpunk", "david", "netflix", "anime", "cyberpunk-edgerunners", "amp", "clear-the-cupboards", "billboard-100"],
        "key_facts": [
            {"label": "Author", "value": "Netflix"},
            {"label": "Published", "value": "2022-10-03T11:00:00-07:00"},
            {"label": "Upload Date", "value": "2022-10-03T11:00:00-07:00"},
            {"label": "Duration", "value": "PT263S"},
            {"label": "Genre", "value": "Entertainment"},
            {"label": "Provider", "value": "YouTube"},
        ],
        "entities": [
            {"type": "VideoObject", "name": "Cyberpunk: Edgerunners | I Really Want to Stay At Your House | Music Video"},
            {"type": "Publisher/Site", "name": "YouTube"},
            {"type": "Author", "name": "@stu92186"},
            {"type": "Author", "name": "Netflix"},
        ],
        "sections": {
            "media": {
                "upload_date": "2022-10-03T11:00:00-07:00",
                "duration": "PT263S",
                "creator": "Netflix",
                "genre": "Entertainment",
            },
            "resource_details": {
                "authors": ["Netflix"],
                "genres": ["Entertainment"],
                "provider_name": "YouTube",
                "media_type": "video",
                "embed_available": True,
                "source_page_date": "2022-10-03",
            },
        },
        "links": {
            "important": [
                {"label": "Netflix", "url": "https://www.youtube.com/channel/UCNETFLIX", "relationship": "internal"},
                {"label": "Instagram", "url": "https://www.youtube.com/redirect?event=Watch_SD_EP&q=https%3A%2F%2Fwww.instagram.com%2Fnetflix%2F", "relationship": "internal"},
                {"label": "4:44", "url": "https://www.youtube.com/watch?v=BnnbP7pCIvQ&list=RDBnnbP7pCIvQ", "relationship": "internal"},
            ]
        },
        "evidence_archive": {
            "links": [
                {"label": "Netflix", "url": "https://www.youtube.com/channel/UCNETFLIX", "relationship": "internal", "region": "body"},
                {"label": "https://lnk.to/irwtsayh", "url": "https://www.youtube.com/redirect?event=video_description&q=https%3A%2F%2Flnk.to%2Firwtsayh", "relationship": "internal", "region": "body"},
                {"label": "Instagram", "url": "https://www.youtube.com/redirect?event=Watch_SD_EP&q=https%3A%2F%2Fwww.instagram.com%2Fnetflix%2F", "relationship": "internal", "region": "body"},
                {"label": "Cyberpunk: Edgerunners — Ending Theme | Let You Down", "url": "https://www.youtube.com/watch?v=BnnbP7pCIvQ", "relationship": "internal", "region": "body"},
                {"label": "The silence of the night Japanese Lo-fi Study Focus", "url": "https://www.youtube.com/watch?v=09K79_bD6w0", "relationship": "internal", "region": "body"},
                {"label": "David Martinez's Lie: What the Game Never Tells You", "url": "https://www.youtube.com/watch?v=2AnDnFtHtng", "relationship": "internal", "region": "body"},
            ]
        },
        "resource_coverage": {
            "html_health_score": 0.43,
            "resource_coverage_score": 0.75,
            "needs_deepening": False,
            "interactive_sections_detected": [
                {"label": "Link"}, {"label": "Comments"}, {"label": "Menu"}, {"label": "Feature"},
            ],
            "covered_sections": ["Link", "Comments", "Feature"],
            "missing_sections": ["Menu"],
        },
        "resource_profile": {"format": "video", "signals": ["anime tag"]},
        "bookmark": {"suggested_tags": []},
        "quality": {"structured_fields_recovered": ["authors", "media_type", "title"], "extraction_score": 0.98},
    }


def _run():
    return finalize_video_resource(_data(), SimpleNamespace(text=HTML, final_url="https://www.youtube.com/watch?v=KvMY1uzSC1E"))


def test_video_creator_is_distinguished_from_commenter():
    data = _run()
    entities = {(row["type"], row["name"]) for row in data["entities"]}
    assert ("Channel/Uploader", "Netflix") in entities
    assert ("Commenter", "@stu92186") in entities
    assert ("Author", "@stu92186") not in entities
    facts = {row["label"]: row["value"] for row in data["key_facts"]}
    assert facts["Channel / Uploader"] == "Netflix"


def test_duration_is_human_readable_and_one_second_player_difference_is_reconciled():
    data = _run()
    media = data["sections"]["media"]
    assert media["duration"] == "4:23"
    assert media["duration_seconds"] == 263
    assert media["duration_iso"] == "PT263S"
    assert media["visible_player_duration"] == "4:22"
    assert media["duration_display_delta_seconds"] == -1
    assert "rounding" in media["duration_timing_note"].lower()
    facts = {row["label"]: row["value"] for row in data["key_facts"]}
    assert facts["Duration"] == "4:23"


def test_video_dates_and_platform_category_are_semantically_normalized():
    data = _run()
    labels = {row["label"] for row in data["key_facts"]}
    assert "Published" not in labels
    assert "Upload Date" in labels
    assert "Genre" not in labels
    assert "YouTube Category" in labels
    resource = data["sections"]["resource_details"]
    assert resource["platform_category"] == "Entertainment"
    assert "genres" not in resource


def test_engagement_is_promoted_from_structured_and_visible_evidence():
    data = _run()
    media = data["sections"]["media"]
    assert media["engagement"]["views"] == "89,115,913"
    assert media["engagement"]["comments"] == "42,998"
    assert media["engagement"]["channel_subscribers"] == "33.6M"
    assert media["engagement"]["likes"] == "1.2M"
    labels = {row["label"] for row in data["key_facts"]}
    assert {"Views", "Comments", "Channel Subscribers", "Likes"} <= labels


def test_longer_structured_video_description_beats_truncated_summary():
    data = _run()
    assert data["summary"].endswith("Netflix history to date.")
    assert not data["summary"].endswith("…")


def test_youtube_redirects_are_unwrapped_and_links_are_curated():
    data = _run()
    links = data["links"]["important"]
    urls = {row["url"] for row in links}
    assert "https://lnk.to/irwtsayh" in urls
    assert "https://www.instagram.com/netflix/" in urls
    assert "https://www.youtube.com/watch?v=BnnbP7pCIvQ" in urls
    assert "https://www.youtube.com/watch?v=2AnDnFtHtng" in urls
    assert "https://www.youtube.com/watch?v=09K79_bD6w0" not in urls
    assert not any("youtube.com/redirect" in row["url"] for row in links)
    roles = {row["relationship"] for row in links}
    assert {"channel", "description_link", "social", "related_video"} <= roles


def test_video_tag_noise_is_removed_without_losing_subject_tags():
    data = _run()
    tags = set(data["tags"])
    assert {"video", "cyberpunk", "netflix", "anime", "cyberpunk-edgerunners"} <= tags
    assert "amp" not in tags
    assert "clear-the-cupboards" not in tags
    assert "billboard-100" not in tags


def test_application_chrome_does_not_lower_video_resource_coverage():
    data = _run()
    coverage = data["resource_coverage"]
    labels = {row["label"] for row in coverage["interactive_sections_detected"]}
    assert "Menu" not in labels
    assert coverage["missing_sections"] == []
    assert coverage["resource_coverage_score"] == 1.0
    assert coverage["needs_deepening"] is False


def test_non_video_resource_is_unchanged():
    data = {"classification": {"kind": "article"}, "identity": {"title": "Example"}}
    acquired = SimpleNamespace(text="<html></html>", final_url="https://example.com")
    assert finalize_video_resource(data, acquired) is data


def test_material_duration_disagreement_is_flagged():
    html = '''<html><body>
    <div>0:00 / 4:40</div>
    <script type="application/ld+json">{"@type": "VideoObject", "duration": "PT263S"}</script>
    </body></html>'''
    data = {
        "classification": {"kind": "video"},
        "sections": {"media": {"duration": "PT263S"}, "resource_details": {}},
        "key_facts": [],
    }
    result = finalize_video_resource(data, SimpleNamespace(text=html, final_url="https://example.com/video"))
    media = result["sections"]["media"]
    assert media["duration"] == "4:23"
    assert media["visible_player_duration"] == "4:40"
    assert media["duration_display_delta_seconds"] == 17
    assert "Material disagreement" in media["duration_timing_note"]


def test_duration_edge_cases_hour_and_seconds_and_int():
    from video_resource import _duration_display, _iso_duration_seconds
    assert _iso_duration_seconds("PT1H02M03S") == 3723
    assert _duration_display(3723) == "1:02:03"
    assert _iso_duration_seconds("PT59S") == 59
    assert _duration_display(59) == "0:59"
    assert _iso_duration_seconds("263") == 263
    assert _duration_display(263) == "4:23"
    assert _iso_duration_seconds(125) == 125
    assert _duration_display(125) == "2:05"


def test_jsonld_comment_schema_author_is_recognized_as_commenter():
    html = '''<html><head>
    <script type="application/ld+json">
    {
      "@type": "VideoObject",
      "name": "Live Sample",
      "author": {"@type": "Person", "name": "Main Creator"},
      "comment": [
        {"@type": "Comment", "author": {"@type": "Person", "name": "@stu92186", "alternateName": "diamondminer97"}}
      ]
    }
    </script>
    </head><body><h1>Live Sample</h1></body></html>'''
    data = {
        "classification": {"kind": "video"},
        "sections": {"media": {}, "resource_details": {"authors": ["Main Creator"]}},
        "entities": [
            {"type": "Author", "name": "Main Creator"},
            {"type": "Author", "name": "@stu92186"},
        ],
        "key_facts": [
            {"label": "Author", "value": "Main Creator"},
            {"label": "Author", "value": "@stu92186"},
        ],
    }
    result = finalize_video_resource(data, SimpleNamespace(text=html, final_url="https://www.youtube.com/watch?v=sample"))
    entities = {(row["type"], row["name"]) for row in result["entities"]}
    assert ("Channel/Uploader", "Main Creator") in entities
    assert ("Commenter", "@stu92186") in entities
    assert ("Author", "@stu92186") not in entities
    facts = {row["label"]: row["value"] for row in result["key_facts"]}
    assert facts.get("Channel / Uploader") == "Main Creator"
    assert facts.get("Author") is None


def test_generic_non_youtube_video_object():
    html = '''<html><head>
    <script type="application/ld+json">
    {
      "@type": "VideoObject",
      "name": "Big Buck Bunny",
      "description": "A large and lovable rabbit deals with bullying forest creatures.",
      "duration": "PT9M56S",
      "uploadDate": "2008-04-10",
      "genre": "Entertainment",
      "interactionStatistic": [
        {"@type": "InteractionCounter", "interactionType": "http://schema.org/WatchAction", "userInteractionCount": 1500000}
      ]
    }
    </script>
    </head><body>
    <h1>Big Buck Bunny</h1>
    </body></html>'''
    data = {
        "classification": {"kind": "video"},
        "sections": {
            "media": {"genre": "Entertainment"},
            "resource_details": {"authors": ["Blender Foundation"], "genres": ["Entertainment"]},
        },
        "key_facts": [
            {"label": "Author", "value": "Blender Foundation"},
            {"label": "Genre", "value": "Entertainment"},
        ],
    }
    result = finalize_video_resource(data, SimpleNamespace(text=html, final_url="https://vimeo.com/1084537"))
    media = result["sections"]["media"]
    resource = result["sections"]["resource_details"]
    assert media["duration"] == "9:56"
    assert media["duration_seconds"] == 596
    assert media["creator"] == "Blender Foundation"
    assert media["engagement"]["views"] == "1,500,000"
    assert resource["platform_category"] == "Entertainment"
    facts = {row["label"]: row["value"] for row in result["key_facts"]}
    assert facts["Channel / Uploader"] == "Blender Foundation"
    assert facts["Platform Category"] == "Entertainment"
    assert "YouTube Category" not in facts

