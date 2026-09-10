from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from video_precision import _youtube_state
from youtube_description_finalize import *


def finalize_youtube_description(data: dict[str, Any], acquired: Any) -> dict[str, Any]:
    """Structure rich YouTube descriptions using only the already-acquired page."""
    kind = str((data.get("classification") or {}).get("kind") or "").casefold()
    media_type = str((((data.get("sections") or {}).get("resource_details") or {}).get("media_type") or "")).casefold()
    page_url = _page_url(data, acquired)
    if kind != "video" and media_type != "video":
        return data
    if not _youtube_host((urlparse(page_url).hostname or "").casefold()):
        return data

    html = str(getattr(acquired, "text", "") or "")
    soup = BeautifulSoup(html, "html.parser")
    player, initial = _youtube_state(html)
    raw = _raw_description(player)

    chapters = _promote_chapters(data, raw, page_url)
    links = _description_links(raw)
    summary = _narrative_summary(raw)
    if summary:
        data["summary"] = summary

    flags = _flags(data, soup)
    _recover_comments(data, initial, soup)
    _recurate_links(data, links)
    _clean_coverage(data, chapters)

    structure = data.setdefault("sections", {}).setdefault("video_structure", {})
    if links:
        structure["description_links"] = links
    if flags:
        structure["resource_flags"] = flags

    quality = data.setdefault("quality", {})
    recovered = set(str(x) for x in (quality.get("structured_fields_recovered") or []))
    if chapters:
        recovered.add("video_chapters")
    if links:
        recovered.add("video_description_links")
    if flags:
        recovered.add("video_resource_flags")
    if (((data.get("sections") or {}).get("media") or {}).get("engagement") or {}).get("comments") is not None:
        recovered.add("video_comments")
    quality["structured_fields_recovered"] = sorted(recovered)

    data["youtube_description_structure"] = {
        "version": DESCRIPTION_VERSION,
        "chapter_count": len(chapters),
        "description_link_count": len(links),
        "resource_flags": sorted(flags),
        "network_requests_added": 0,
    }
    return data


__all__ = [name for name in globals() if not name.startswith("__")]
