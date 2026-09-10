from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

from video_extract import *


def _same_date(a: Any, b: Any) -> bool:
    left, right = str(a or ""), str(b or "")
    return bool(left and right and left[:10] == right[:10])


def _set_fact(facts: list[dict[str, Any]], label: str, value: Any) -> None:
    text = _clean(value, 500)
    if not text:
        return
    for row in facts:
        if _norm(row.get("label")) == _norm(label):
            row["label"] = label
            row["value"] = text
            return
    facts.append({"label": label, "value": text})


def _extract_jsonld_commenters(soup: BeautifulSoup) -> set[str]:
    commenters: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            raw_type = node.get("@type")
            types = {raw_type} if isinstance(raw_type, str) else set(raw_type or []) if isinstance(raw_type, list) else set()
            types_norm = {_norm(item) for item in types}
            if "comment" in types_norm or any("comment" in item for item in types_norm):
                author = node.get("author")
                if isinstance(author, dict):
                    for key in ("name", "alternateName"):
                        value = _clean(author.get(key), 200)
                        if value:
                            commenters.add(value)
                    match = re.search(r"/@([^/?#]+)", str(author.get("url") or ""))
                    if match:
                        commenters.add(f"@{match.group(1)}")
                        commenters.add(match.group(1))
                elif isinstance(author, str):
                    value = _clean(author, 200)
                    if value:
                        commenters.add(value)
            comments = node.get("comment")
            if comments:
                if isinstance(comments, dict):
                    comments = [comments]
                if isinstance(comments, list):
                    for comment in comments:
                        if not isinstance(comment, dict):
                            continue
                        author = comment.get("author")
                        if isinstance(author, dict):
                            for key in ("name", "alternateName"):
                                value = _clean(author.get(key), 200)
                                if value:
                                    commenters.add(value)
                            match = re.search(r"/@([^/?#]+)", str(author.get("url") or ""))
                            if match:
                                commenters.add(f"@{match.group(1)}")
                                commenters.add(match.group(1))
                        elif isinstance(author, str):
                            value = _clean(author, 200)
                            if value:
                                commenters.add(value)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        raw = script.string or script.get_text("", strip=False)
        if not raw:
            continue
        try:
            walk(json.loads(raw))
        except Exception:
            continue
    return commenters


def _commenter_handles(soup: BeautifulSoup) -> set[str]:
    handles = _extract_jsonld_commenters(soup)
    html = str(soup)
    handles.update(re.findall(r'"authorText"\s*:\s*\{[^{}]{0,300}?"simpleText"\s*:\s*"(@[^"\\]{2,80})"', html, re.I))
    handles.update(re.findall(r'"authorText"\s*:\s*\{[^{}]{0,500}?"runs"\s*:\s*\[\s*\{\s*"text"\s*:\s*"(@[^"\\]{2,80})"', html, re.I))
    handles.update(re.findall(r'"author"\s*:\s*\{[^{}]{0,400}?"name"\s*:\s*"(@[^"\\]{2,80})"', html, re.I))
    return handles


def _promote_video_fields(data: dict[str, Any], video: dict[str, Any] | None, soup: BeautifulSoup, commenters: set[str] | None = None) -> None:
    sections = data.setdefault("sections", {})
    media = sections.setdefault("media", {})
    resource = sections.setdefault("resource_details", {})
    facts = data.setdefault("key_facts", [])
    provider_authors = resource.get("authors") or []
    if not isinstance(provider_authors, list):
        provider_authors = [provider_authors]
    author_norms = {_norm(x) for x in provider_authors if _clean(x, 200)}
    commenter_norms = {_norm(x) for x in (commenters or set()) if _clean(x, 200) and _norm(x) not in author_norms}
    clean_authors = [x for x in (_clean(value, 200) for value in provider_authors) if x and _norm(x) not in commenter_norms and not x.startswith("@")]
    creator = clean_authors[0] if clean_authors else _clean(media.get("creator"), 200)
    if creator and (_norm(creator) in commenter_norms or creator.startswith("@")):
        creator = None
    if not creator and video and video.get("author"):
        candidate = video.get("author")
        if isinstance(candidate, dict):
            candidate = candidate.get("name")
        candidate = _clean(candidate, 200)
        if candidate and _norm(candidate) not in commenter_norms and not candidate.startswith("@"):
            creator = candidate
    if creator:
        media["creator"] = creator
        media["channel"] = creator
        media["uploader"] = creator
        resource["channel_name"] = creator
        resource["uploader"] = creator
        for row in facts:
            if _norm(row.get("label")) == "author" and (_norm(row.get("value")) == _norm(creator) or not row.get("value")):
                row["label"] = "Channel / Uploader"
        _set_fact(facts, "Channel / Uploader", creator)

    upload_date = media.get("upload_date") or resource.get("upload_date") or (video or {}).get("uploadDate")
    if upload_date:
        media["upload_date"] = upload_date
        resource["upload_date"] = upload_date
        _set_fact(facts, "Upload Date", upload_date)
        facts[:] = [row for row in facts if not (_norm(row.get("label")) == "published" and _same_date(row.get("value"), upload_date))]

    raw_duration = media.get("duration") or resource.get("duration") or (video or {}).get("duration")
    duration_seconds = _iso_duration_seconds(raw_duration)
    if duration_seconds is not None:
        display = _duration_display(duration_seconds)
        visible, visible_seconds = _visible_player_duration(soup, duration_seconds)
        media.update({"duration": display, "duration_seconds": duration_seconds, "duration_iso": str(raw_duration)})
        resource.update({"duration": display, "duration_seconds": duration_seconds, "duration_iso": str(raw_duration)})
        if visible and visible_seconds is not None:
            media["visible_player_duration"] = visible
            delta = visible_seconds - duration_seconds
            media["duration_display_delta_seconds"] = delta
            if abs(delta) <= 2 and delta != 0:
                media["duration_timing_note"] = "Structured duration and visible player duration differ by <=2s; treated as player/display rounding."
            elif abs(delta) > 2:
                media["duration_timing_note"] = f"Material disagreement between structured duration ({display}) and visible player duration ({visible})."
        _set_fact(facts, "Duration", display)

    raw_category = resource.get("genres") or media.get("genre")
    if isinstance(raw_category, list) and len(raw_category) == 1:
        raw_category = raw_category[0]
    page_host = _host(str((data.get("fetch") or {}).get("final_url") or (data.get("input") or {}).get("url") or ""))
    if raw_category and (_norm(raw_category) == "entertainment" or _youtube_host(page_host)):
        resource["platform_category"] = raw_category
        media["platform_category"] = raw_category
        resource.pop("genres", None)
        media.pop("genre", None)
        category_label = "YouTube Category" if _youtube_host(page_host) else "Platform Category"
        for row in facts:
            if _norm(row.get("label")) == "genre" and _norm(row.get("value")) == _norm(raw_category):
                row["label"] = category_label
        _set_fact(facts, category_label, raw_category)

    engagement = _engagement_from_video_object(video)
    _augment_engagement_from_page(soup, engagement)
    if engagement:
        compact: dict[str, Any] = {}
        for key, row in engagement.items():
            compact[key] = row.get("display") or (f"{row.get('count'):,}" if row.get("count") is not None else None)
            resource[f"{key}_count"] = row.get("count")
            resource[f"{key}_display"] = compact[key]
        media["engagement"] = compact
        labels = {"views": "Views", "likes": "Likes", "comments": "Comments", "channel_subscribers": "Channel Subscribers"}
        for key, label in labels.items():
            if key in engagement:
                _set_fact(facts, label, engagement[key].get("display"))

    description = _description_candidate(video, soup)
    current = _clean(data.get("summary"), 1600)
    if description and (not current or current.endswith(("...", "…")) or len(description) >= len(current) + 80):
        data["summary"] = description


def _fix_entities(data: dict[str, Any], soup: BeautifulSoup, commenters: set[str] | None = None) -> None:
    resource = (data.get("sections") or {}).get("resource_details") or {}
    authors = resource.get("authors") or []
    if not isinstance(authors, list):
        authors = [authors]
    author_norms = {_norm(x) for x in authors if _clean(x, 200)}
    commenter_set = set(commenters or _commenter_handles(soup))
    commenter_norms = {_norm(x) for x in commenter_set if _clean(x, 200)}
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for entity in data.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        name = _clean(entity.get("name"), 200)
        entity_type = _clean(entity.get("type"), 100) or "Entity"
        if not name:
            continue
        name_norm = _norm(name)
        type_norm = _norm(entity_type)
        if type_norm in {"author", "person author", "person/author", "creator", "social/creator"} and name_norm in author_norms:
            entity_type = "Channel/Uploader"
        elif type_norm in {"author", "person author", "person/author", "creator", "social/creator"} and (name_norm in commenter_norms or name.startswith("@")):
            entity_type = "Commenter"
        key = (_norm(entity_type), name_norm)
        if key not in seen:
            seen.add(key)
            out.append({**entity, "type": entity_type, "name": name})
    for author in authors:
        name = _clean(author, 200)
        if not name or _norm(name) in commenter_norms or name.startswith("@"):
            continue
        key = (_norm("Channel/Uploader"), _norm(name))
        if key not in seen:
            seen.add(key)
            out.append({"type": "Channel/Uploader", "name": name})
    data["entities"] = out
    facts = data.setdefault("key_facts", [])
    facts[:] = [
        row for row in facts
        if not (
            _norm(row.get("label")) in {"author", "person author", "person/author", "creator"}
            and (_norm(row.get("value")) in commenter_norms or str(row.get("value") or "").startswith("@"))
            and _norm(row.get("value")) not in author_norms
        )
    ]


__all__ = [name for name in globals() if not name.startswith("__")]
