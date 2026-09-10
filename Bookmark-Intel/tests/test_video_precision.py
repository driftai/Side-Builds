from __future__ import annotations

import copy
import json
from types import SimpleNamespace

from video_precision import finalize_video_precision


def _base(title: str, author: str = "Netflix") -> dict:
    return {
        "input": {"url": "https://www.youtube.com/watch?v=sample"},
        "fetch": {"final_url": "https://www.youtube.com/watch?v=sample"},
        "classification": {"kind": "video"},
        "identity": {"title": title},
        "summary": f"{title} {title} {author} 4 views If playback doesn't begin shortly, try restarting your device.",
        "tags": ["video", "sharing", "camera-phone", "video-phone", "free", "upload", "music", "people-blogs"],
        "key_facts": [{"label": "Provider", "value": "YouTube"}],
        "entities": [
            {"type": "Publisher/Site", "name": "YouTube"},
            {"type": "Author", "name": author},
            {"type": "Author", "name": "Recommendation Author"},
        ],
        "sections": {
            "media": {},
            "resource_details": {"authors": [author], "media_type": "video", "provider_name": "YouTube"},
        },
        "links": {"important": []},
        "evidence_archive": {"links": []},
        "resource_coverage": {
            "resource_coverage_score": 0.5,
            "needs_deepening": True,
            "interactive_sections_detected": [{"label": "Link"}, {"label": "Feature"}],
            "covered_sections": ["Link"],
            "missing_sections": ["Feature"],
        },
        "bookmark": {},
        "quality": {"structured_fields_recovered": []},
    }


def _html(player: dict, initial: dict | None = None, clock: str = "0:00 / 4:22") -> str:
    initial = initial or {}
    return (
        f"<html><body><div>{clock}</div>"
        f"<script>var ytInitialPlayerResponse = {json.dumps(player)};</script>"
        f"<script>var ytInitialData = {json.dumps(initial)};</script>"
        "</body></html>"
    )


def test_sparse_youtube_player_state_recovers_video_fields_and_replaces_chrome_summary():
    title = "Cyberpunk: Edgerunners | I Really Want to Stay At Your House | Music Video"
    data = _base(title)
    player = {
        "videoDetails": {
            "title": title,
            "author": "Netflix",
            "lengthSeconds": "263",
            "viewCount": "89115913",
            "shortDescription": (
                "Thank you to all of the incredible artists who contributed to the magic that is "
                "Cyberpunk: Edgerunners, and to all of the fans who blew the show up to create one "
                "of the most memorable anime of Netflix history to date."
            ),
            "keywords": ["cyberpunk", "cyberpunk edgerunners", "anime"],
        },
        "microformat": {"playerMicroformatRenderer": {"category": "Entertainment", "uploadDate": "2022-10-03"}},
    }
    initial = {
        "header": {"subscriberCountText": {"simpleText": "33.6M subscribers"}},
        "like": {"accessibilityText": "1.2M likes"},
        "comments": {"simpleText": "42,998 Comments"},
    }

    out = finalize_video_precision(
        data,
        SimpleNamespace(text=_html(player, initial), final_url="https://www.youtube.com/watch?v=sample"),
    )
    media = out["sections"]["media"]
    resource = out["sections"]["resource_details"]

    assert media["creator"] == "Netflix"
    assert media["duration"] == "4:23"
    assert media["duration_seconds"] == 263
    assert media["visible_player_duration"] == "4:22"
    assert media["duration_display_delta_seconds"] == -1
    assert media["platform_category"] == "Entertainment"
    assert media["engagement"] == {
        "views": "89,115,913",
        "likes": "1.2M",
        "comments": "42,998",
        "channel_subscribers": "33.6M",
    }
    assert resource["views_count"] == 89115913
    assert out["summary"].startswith("Thank you to all of the incredible artists")
    assert out["resource_coverage"]["resource_coverage_score"] == 1.0
    assert out["resource_coverage"]["missing_sections"] == []
    assert out["video_precision"]["youtube_player_state_used"] is True


def test_recommendation_author_does_not_become_bookmarked_video_author():
    title = "Roblox Piano Cover of My Dearest - Guilty Crown OP1 [Piano]"
    data = _base(title, "alvigod OP")
    data["entities"] = [
        {"type": "VideoObject", "name": title},
        {"type": "Publisher/Site", "name": "YouTube"},
        {"type": "Channel/Uploader", "name": "alvigod OP"},
        {"type": "Author", "name": "Erik C"},
    ]
    player = {
        "videoDetails": {"title": title, "author": "alvigod OP", "lengthSeconds": "420", "viewCount": "4"},
        "microformat": {"playerMicroformatRenderer": {"category": "People & Blogs"}},
    }
    out = finalize_video_precision(
        data,
        SimpleNamespace(text=_html(player, clock="0:00 / 6:59"), final_url="https://www.youtube.com/watch?v=sample"),
    )
    assert not any(row.get("name") == "Erik C" for row in out["entities"])
    assert any(row.get("type") == "Channel/Uploader" and row.get("name") == "alvigod OP" for row in out["entities"])


def test_description_credit_beats_loose_recommendations_and_tags_are_subject_focused():
    title = "Roblox Piano Cover of My Dearest - Guilty Crown OP1 [Piano]"
    data = _base(title, "alvigod OP")
    data["evidence_archive"]["links"] = [
        {
            "label": "• My Dearest - Guilty Crown OP1 [Piano]",
            "url": "https://www.youtube.com/watch?v=Pi8xsZXibIc",
            "source_context": "Description",
        },
        {
            "label": "Roblox Piano Cover of A Rusty Dream (from Cyberpunk: Edgerunners 2) alvigod OP",
            "url": "https://www.youtube.com/watch?v=hsXsfPD3vbQ",
        },
        {
            "label": "Call of Silence (Ymir's theme) - Attack on Titan S2 OST [Piano]",
            "url": "https://www.youtube.com/watch?v=5Ggnzs2hP3s",
        },
        {"label": "www.youtube.com", "url": "https://www.youtube.com/@alvigodop", "source_context": "Description"},
    ]
    player = {
        "videoDetails": {
            "title": title,
            "author": "alvigod OP",
            "lengthSeconds": "420",
            "viewCount": "4",
            "shortDescription": "Credit to\n• My Dearest - Guilty Crown OP1 [Piano]",
            "keywords": ["sharing", "camera phone", "video phone", "free", "upload", "music"],
        },
        "microformat": {"playerMicroformatRenderer": {"category": "People & Blogs"}},
    }
    out = finalize_video_precision(
        data,
        SimpleNamespace(text=_html(player, clock="0:00 / 6:59"), final_url="https://www.youtube.com/watch?v=sample"),
    )

    assert out["summary"].startswith("Credit to")
    links = out["links"]["important"]
    assert any("Pi8xsZXibIc" in row["url"] and row["curation_role"] in {"credited_source", "description_link"} for row in links)
    assert not any("hsXsfPD3vbQ" in row["url"] for row in links)
    assert not any("5Ggnzs2hP3s" in row["url"] for row in links)

    tags = set(out["tags"])
    assert {"video", "roblox", "piano", "cover", "dearest", "guilty", "crown", "my-dearest", "guilty-crown"} <= tags
    assert not {"sharing", "camera-phone", "video-phone", "free", "upload", "people-blogs"} & tags


def test_recommendation_season_episode_and_feature_do_not_count_as_video_coverage_sections():
    data = _base("Example Video")
    data["resource_coverage"] = {
        "resource_coverage_score": 0.4,
        "needs_deepening": True,
        "interactive_sections_detected": [
            {"label": "Link"}, {"label": "Comments"}, {"label": "Feature"}, {"label": "Season"}, {"label": "Episode"}
        ],
        "covered_sections": ["Link", "Comments"],
        "missing_sections": ["Feature", "Season", "Episode"],
    }
    out = finalize_video_precision(
        data,
        SimpleNamespace(text="<html><body></body></html>", final_url="https://www.youtube.com/watch?v=sample"),
    )
    assert [row["label"] for row in out["resource_coverage"]["interactive_sections_detected"]] == ["Link", "Comments"]
    assert out["resource_coverage"]["resource_coverage_score"] == 1.0
    assert out["resource_coverage"]["needs_deepening"] is False


def test_evidence_archive_is_preserved_and_non_youtube_video_is_unchanged():
    data = _base("Example Video")
    data["evidence_archive"] = {
        "links": [{"label": "Raw", "url": "https://example.com/raw"}],
        "labeled_facts": [{"label": "X", "value": "Y"}],
    }
    before_archive = copy.deepcopy(data["evidence_archive"])
    out = finalize_video_precision(
        data,
        SimpleNamespace(text="<html></html>", final_url="https://www.youtube.com/watch?v=sample"),
    )
    assert out["evidence_archive"] == before_archive

    vimeo = _base("Generic Vimeo Video")
    vimeo_before = copy.deepcopy(vimeo)
    result = finalize_video_precision(vimeo, SimpleNamespace(text="<html></html>", final_url="https://vimeo.com/123"))
    assert result == vimeo_before


def test_creator_fallback_and_credited_source_variants():
    title = "Roblox Piano Cover of My Dearest - Guilty Crown OP1 [Piano]"
    data = _base(title, "Fallback Channel")
    data["sections"]["media"]["creator"] = "Fallback Channel"
    data["key_facts"] = [
        {"label": "Author", "value": "Rogue Recommendation Author"},
    ]
    data["summary"] = "Original song: • My Dearest - Guilty Crown OP1 [Piano]"
    data["evidence_archive"]["links"] = [
        {
            "label": "• My Dearest - Guilty Crown OP1 [Piano]",
            "url": "https://www.youtube.com/watch?v=Pi8xsZXibIc",
            "source_context": "Description",
        }
    ]
    player = {"videoDetails": {"title": title, "lengthSeconds": "420"}}
    out = finalize_video_precision(
        data,
        SimpleNamespace(text=_html(player, clock="0:00 / 6:59"), final_url="https://www.youtube.com/watch?v=sample"),
    )
    facts = {row["label"]: row["value"] for row in out["key_facts"]}
    assert facts.get("Channel / Uploader") == "Fallback Channel"
    assert facts.get("Author") is None
    links = out["links"]["important"]
    assert any(row["relationship"] == "credited_source" for row in links)

