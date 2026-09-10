from __future__ import annotations

import copy
import json
from types import SimpleNamespace

from youtube_description import finalize_youtube_description


def _base() -> dict:
    return {
        "input": {"url": "https://www.youtube.com/watch?v=challenge"},
        "fetch": {"final_url": "https://www.youtube.com/watch?v=challenge"},
        "classification": {"kind": "video"},
        "identity": {"title": "Build & Battle your Custom Trading Card in our New 3D Art Challenge | Gauntlet of Gods"},
        "summary": "Accept the Challenge: https://example.com ... CHAPTERS: 00:00 Intro ...",
        "key_facts": [{"label": "Provider", "value": "YouTube"}],
        "entities": [],
        "sections": {
            "media": {
                "creator": "pwnisher",
                "engagement": {"views": "69,491", "likes": "3,160", "channel_subscribers": "1.4M"},
            },
            "resource_details": {
                "authors": ["pwnisher"],
                "media_type": "video",
                "provider_name": "YouTube",
                "chapters": "View all",
            },
        },
        "links": {
            "important": [
                {
                    "label": "pwnisher",
                    "url": "https://www.youtube.com/channel/UCWIfzAYHyNSyHmT2AO-54yg",
                    "relationship": "channel",
                    "curation_role": "channel",
                    "curation_score": 0.96,
                },
                {
                    "label": "pwnisher",
                    "url": "https://www.youtube.com/@pwnisher",
                    "relationship": "channel",
                    "curation_role": "channel",
                    "curation_score": 0.94,
                },
                {
                    "label": "Learn more",
                    "url": "https://support.google.com/youtube/answer/15569972?hl=en",
                    "relationship": "description_link",
                    "curation_role": "description_link",
                    "curation_score": 0.98,
                },
                {
                    "label": "NEW 3D Challenge Launch Stream! | GAUNTLET OF GODS",
                    "url": "https://www.youtube.com/watch?v=MbeNmDYLP9w",
                    "relationship": "related_video",
                    "curation_role": "related_video",
                    "curation_score": 0.84,
                },
            ]
        },
        "evidence_archive": {
            "links": [{"label": "Raw help", "url": "https://support.google.com/youtube/answer/15569972"}],
            "labeled_facts": [{"label": "Chapters", "value": "View all"}],
            "grouped_values": [],
        },
        "resource_coverage": {
            "resource_coverage_score": 1.0,
            "needs_deepening": False,
            "interactive_sections_detected": [
                {"label": "Chapters"},
                {"label": "Link"},
                {"label": "Comments"},
                {"label": "Comment"},
                {"label": "Chapter"},
                {"label": "Overview"},
                {"label": "History"},
            ],
            "covered_sections": ["Chapters", "Link", "Comments", "Comment", "Chapter", "Overview", "History"],
            "missing_sections": [],
        },
        "quality": {"structured_fields_recovered": []},
    }


DESCRIPTION = """Accept the Challenge: https://www.createwithclint.com/gauntletofgods
Pre-Order the Physical Game: https://creocards.com/collections/gauntlet-of-gods
Play the Online Card Game: https://play.gauntletofgods.com/
Get Started Livestream: https://youtube.com/live/MbeNmDYLP9w?feature=share

Through the month of August we're challenging 3D artists to create their very own animated trading card!
We're hooking you up with a 3D template and 13 hand-animated rigs so you can focus on designing your character.
After the August 31st deadline, selected entries will become part of a free community-built card game and the best 100 submissions will receive a limited physical print run.

*CHAPTERS:*
00:00 Intro
00:21 Challenge Overview
01:05 The Card Game
01:56 Get Started & Free Tools
03:27 The Rules
07:57 Challenge Advice & Guest Judges
09:08 Prizes

*SPONSORS:*
Marvelous Designer: https://www.marvelousdesigner.com/gauntletofgods
Rokoko: https://glnk.io/pwnisher

*WITH GUESTS:*
Wilbert Roget II: https://example.com/wilbert
"""


def _html(description: str = DESCRIPTION) -> str:
    player = {
        "videoDetails": {
            "title": "Build & Battle your Custom Trading Card in our New 3D Art Challenge | Gauntlet of Gods",
            "author": "pwnisher",
            "shortDescription": description,
            "lengthSeconds": "969",
            "viewCount": "69491",
        }
    }
    initial = {"commentsHeader": {"simpleText": "265 Comments"}}
    return (
        "<html><body>"
        "<div>Includes paid promotion</div>"
        "<div>69,491 views • Premiered Aug 1, 2026</div>"
        "<div>How this was made Auto-dubbed Audio tracks for some languages were automatically generated.</div>"
        "<div>Transcript Follow along using the transcript. Show transcript</div>"
        f"<script>var ytInitialPlayerResponse = {json.dumps(player)};</script>"
        f"<script>var ytInitialData = {json.dumps(initial)};</script>"
        "</body></html>"
    )


def _run(data: dict | None = None, description: str = DESCRIPTION) -> dict:
    return finalize_youtube_description(
        data or _base(),
        SimpleNamespace(text=_html(description), final_url="https://www.youtube.com/watch?v=challenge"),
    )


def test_rich_description_becomes_narrative_summary_and_structured_chapters():
    out = _run()
    assert out["summary"].startswith("Through the month of August")
    assert "SPONSORS" not in out["summary"]
    assert "CHAPTERS" not in out["summary"]

    chapters = out["sections"]["resource_details"]["chapters"]
    assert [row["title"] for row in chapters] == [
        "Intro",
        "Challenge Overview",
        "The Card Game",
        "Get Started & Free Tools",
        "The Rules",
        "Challenge Advice & Guest Judges",
        "Prizes",
    ]
    assert chapters[1]["seconds"] == 21
    assert chapters[1]["url"] == "https://www.youtube.com/watch?v=challenge&t=21s"
    assert out["youtube_description_structure"]["chapter_count"] == 7
    assert any(row.get("label") == "Chapters" and row.get("value") == "7" for row in out["key_facts"])


def test_labeled_description_links_are_semantic_and_channel_duplicates_and_help_are_removed():
    out = _run()
    links = out["links"]["important"]

    assert any(row["label"] == "Accept the Challenge" and row["relationship"] == "challenge" for row in links)
    assert any(row["label"] == "Pre-Order the Physical Game" and row["relationship"] == "store" for row in links)
    assert any(row["label"] == "Play the Online Card Game" and row["relationship"] == "game" for row in links)
    assert any(row["label"] == "Get Started Livestream" and row["relationship"] == "livestream" for row in links)
    assert any(row["label"] == "Marvelous Designer" and row["relationship"] == "sponsor" for row in links)
    assert not any("support.google.com" in row["url"] for row in links)
    assert sum(1 for row in links if row["relationship"] == "channel") == 1

    livestream = next(row for row in links if row["relationship"] == "livestream")
    assert livestream["url"] == "https://www.youtube.com/watch?v=MbeNmDYLP9w"


def test_flags_and_missing_comment_count_are_promoted():
    out = _run()
    resource = out["sections"]["resource_details"]
    engagement = out["sections"]["media"]["engagement"]

    assert resource["paid_promotion"] is True
    assert resource["publication_mode"] == "Premiere"
    assert resource["transcript_available"] is True
    assert resource["auto_dubbed_audio"] is True
    assert engagement["comments"] == "265"
    assert resource["comments_count"] == 265

    facts = {row["label"]: row["value"] for row in out["key_facts"]}
    assert facts["Paid promotion"] == "Yes"
    assert facts["Publication Mode"] == "Premiere"
    assert facts["Transcript Available"] == "Yes"
    assert facts["Auto-dubbed Audio"] == "Yes"
    assert facts["Comments"] == "265"


def test_false_youtube_coverage_labels_are_removed_and_chapter_singular_is_deduped():
    out = _run()
    coverage = out["resource_coverage"]
    labels = [row["label"] for row in coverage["interactive_sections_detected"]]

    assert labels == ["Chapters", "Link", "Comments"]
    assert coverage["covered_sections"] == ["Chapters", "Link", "Comments"]
    assert coverage["missing_sections"] == []
    assert coverage["resource_coverage_score"] == 1.0
    assert coverage["needs_deepening"] is False


def test_short_credit_only_description_is_not_rewritten_into_an_empty_narrative():
    data = _base()
    data["summary"] = "Credit to https://youtu.be/Pi8xsZXibIc"
    description = "Credit to https://youtu.be/Pi8xsZXibIc"
    out = _run(data, description)
    assert out["summary"] == "Credit to https://youtu.be/Pi8xsZXibIc"


def test_evidence_archive_is_untouched_and_non_youtube_video_is_noop():
    data = _base()
    before_archive = copy.deepcopy(data["evidence_archive"])
    out = _run(data)
    assert out["evidence_archive"] == before_archive

    non_youtube = _base()
    before = copy.deepcopy(non_youtube)
    result = finalize_youtube_description(
        non_youtube,
        SimpleNamespace(text="<html></html>", final_url="https://vimeo.com/123"),
    )
    assert result == before


def test_truncated_existing_link_is_upgraded_by_semantic_description_link():
    data = _base()
    data["links"]["important"].append(
        {
            "label": "https://creocards.com/collections/gau...",
            "url": "https://creocards.com/collections/gauntlet-of-gods",
            "relationship": "description_link",
            "curation_role": "description_link",
            "curation_score": 0.98,
            "source_context": "Description",
            "unwrapped_from": "https://www.youtube.com/redirect?q=...",
        }
    )
    out = _run(data)
    match = next(
        (row for row in out["links"]["important"] if "creocards.com" in row["url"]),
        None,
    )
    assert match is not None
    assert match["label"] == "Pre-Order the Physical Game"
    assert match["relationship"] == "store"
    assert match["curation_role"] == "store"
    assert match["source_context"] == "Description"
    assert match["unwrapped_from"] == "https://www.youtube.com/redirect?q=..."


def test_callout_links_are_excluded_from_narrative_summary():
    desc = (
        "Through the month of August we're challenging 3D artists to create their very own animated trading card! "
        "We're hooking you up with a 3D template and 13 hand-animated rigs so you can focus on designing your character. "
        "After the August 31st deadline, selected entries will become part of a free community-built card game and the best 100 submissions will receive a limited physical print run.\n"
        "Check out UNESCO's International Fund for Cultural Diversity: https://www.unesco.org/creativity/en/international-fund-cultural-diversity\n"
        "\n*CHAPTERS:*\n00:00 Intro\n01:00 Outro\n"
    )
    out = _run(description=desc)
    assert out["summary"].startswith("Through the month of August")
    assert out["summary"].endswith("limited physical print run.")
    assert "Check out UNESCO" not in out["summary"]

