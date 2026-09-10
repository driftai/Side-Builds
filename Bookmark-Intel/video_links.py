from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any
from urllib.parse import parse_qs, urlparse

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
            types_norm = {_norm(t) for t in types}
            if "comment" in types_norm or any("comment" in t for t in types_norm):
                author = node.get("author")
                if isinstance(author, dict):
                    for k in ("name", "alternateName"):
                        val = _clean(author.get(k), 200)
                        if val: commenters.add(val)
                    if handle_m := re.search(r"/@([^/?#]+)", str(author.get("url") or "")):
                        commenters.add(f"@{handle_m.group(1)}"); commenters.add(handle_m.group(1))
                elif isinstance(author, str):
                    val = _clean(author, 200)
                    if val: commenters.add(val)
            comments = node.get("comment")
            if comments:
                if isinstance(comments, dict): comments = [comments]
                if isinstance(comments, list):
                    for c in comments:
                        if not isinstance(c, dict): continue
                        author = c.get("author")
                        if isinstance(author, dict):
                            for k in ("name", "alternateName"):
                                val = _clean(author.get(k), 200)
                                if val: commenters.add(val)
                            if handle_m := re.search(r"/@([^/?#]+)", str(author.get("url") or "")):
                                commenters.add(f"@{handle_m.group(1)}"); commenters.add(handle_m.group(1))
                        elif isinstance(author, str):
                            val = _clean(author, 200)
                            if val: commenters.add(val)
            for v in node.values(): walk(v)
        elif isinstance(node, list):
            for item in node: walk(item)
    for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        raw = script.string or script.get_text("", strip=False)
        if not raw: continue
        try: walk(json.loads(raw))
        except Exception: continue
    return commenters


def _commenter_handles(soup: BeautifulSoup) -> set[str]:
    handles = _extract_jsonld_commenters(soup); html = str(soup)
    handles.update(re.findall(r'"authorText"\s*:\s*\{[^{}]{0,300}?"simpleText"\s*:\s*"(@[^"\\]{2,80})"', html, re.I))
    handles.update(re.findall(r'"authorText"\s*:\s*\{[^{}]{0,500}?"runs"\s*:\s*\[\s*\{\s*"text"\s*:\s*"(@[^"\\]{2,80})"', html, re.I))
    handles.update(re.findall(r'"author"\s*:\s*\{[^{}]{0,400}?"name"\s*:\s*"(@[^"\\]{2,80})"', html, re.I))
    return handles


def _promote_video_fields(data: dict[str, Any], video: dict[str, Any] | None, soup: BeautifulSoup, commenters: set[str] | None = None) -> None:
    sections = data.setdefault("sections", {}); media = sections.setdefault("media", {}); resource = sections.setdefault("resource_details", {}); facts = data.setdefault("key_facts", [])
    provider_authors = resource.get("authors") or []
    if not isinstance(provider_authors, list): provider_authors = [provider_authors]
    author_norms = {_norm(x) for x in provider_authors if _clean(x, 200)}
    commenter_norms = {_norm(x) for x in (commenters or set()) if _clean(x, 200) and _norm(x) not in author_norms}
    clean_authors = [x for x in (_clean(v, 200) for v in provider_authors) if x and _norm(x) not in commenter_norms and not x.startswith("@")]
    creator = clean_authors[0] if clean_authors else _clean(media.get("creator"), 200)
    if creator and (_norm(creator) in commenter_norms or creator.startswith("@")): creator = None
    if not creator and video and video.get("author"):
        cand = video.get("author"); cand = cand.get("name") if isinstance(cand, dict) else cand; cleaned = _clean(cand, 200)
        if cleaned and _norm(cleaned) not in commenter_norms and not cleaned.startswith("@"): creator = cleaned
    if creator:
        media.update(creator=creator, channel=creator, uploader=creator); resource.update(channel_name=creator, uploader=creator)
        for row in facts:
            if _norm(row.get("label")) == "author" and (_norm(row.get("value")) == _norm(creator) or not row.get("value")): row["label"] = "Channel / Uploader"
        _set_fact(facts, "Channel / Uploader", creator)
    upload_date = media.get("upload_date") or resource.get("upload_date") or (video or {}).get("uploadDate")
    if upload_date:
        media["upload_date"] = resource["upload_date"] = upload_date; _set_fact(facts, "Upload Date", upload_date)
        facts[:] = [row for row in facts if not (_norm(row.get("label")) == "published" and _same_date(row.get("value"), upload_date))]
    raw_duration = media.get("duration") or resource.get("duration") or (video or {}).get("duration")
    duration_seconds = _iso_duration_seconds(raw_duration)
    if duration_seconds is not None:
        display = _duration_display(duration_seconds); visible, visible_seconds = _visible_player_duration(soup, duration_seconds)
        media.update(duration=display, duration_seconds=duration_seconds, duration_iso=str(raw_duration)); resource.update(duration=display, duration_seconds=duration_seconds, duration_iso=str(raw_duration))
        if visible and visible_seconds is not None:
            delta = visible_seconds - duration_seconds; media.update(visible_player_duration=visible, duration_display_delta_seconds=delta)
            if abs(delta) <= 2 and delta != 0: media["duration_timing_note"] = "Structured duration and visible player duration differ by <=2s; treated as player/display rounding."
            elif abs(delta) > 2: media["duration_timing_note"] = f"Material disagreement between structured duration ({display}) and visible player duration ({visible})."
        _set_fact(facts, "Duration", display)
    raw_category = resource.get("genres") or media.get("genre")
    if isinstance(raw_category, list) and len(raw_category) == 1: raw_category = raw_category[0]
    page_host = _host(str((data.get("fetch") or {}).get("final_url") or (data.get("input") or {}).get("url") or ""))
    if raw_category and (_norm(raw_category) == "entertainment" or _youtube_host(page_host)):
        resource["platform_category"] = media["platform_category"] = raw_category; resource.pop("genres", None); media.pop("genre", None)
        category_label = "YouTube Category" if _youtube_host(page_host) else "Platform Category"
        for row in facts:
            if _norm(row.get("label")) == "genre" and _norm(row.get("value")) == _norm(raw_category): row["label"] = category_label
        _set_fact(facts, category_label, raw_category)
    engagement = _engagement_from_video_object(video); _augment_engagement_from_page(soup, engagement)
    if engagement:
        compact: dict[str, Any] = {}
        for key, row in engagement.items():
            compact[key] = row.get("display") or (f"{row.get('count'):,}" if row.get("count") is not None else None); resource[f"{key}_count"] = row.get("count"); resource[f"{key}_display"] = compact[key]
        media["engagement"] = compact
        for key, label in {"views": "Views", "likes": "Likes", "comments": "Comments", "channel_subscribers": "Channel Subscribers"}.items():
            if key in engagement: _set_fact(facts, label, engagement[key].get("display"))
    description = _description_candidate(video, soup); current = _clean(data.get("summary"), 1600)
    if description and (not current or current.endswith(("...", "…")) or len(description) >= len(current) + 80): data["summary"] = description


def _fix_entities(data: dict[str, Any], soup: BeautifulSoup, commenters: set[str] | None = None) -> None:
    resource = (data.get("sections") or {}).get("resource_details") or {}; authors = resource.get("authors") or []
    if not isinstance(authors, list): authors = [authors]
    author_norms = {_norm(x) for x in authors if _clean(x, 200)}; commenter_set = set(commenters or _commenter_handles(soup)); commenter_norms = {_norm(x) for x in commenter_set if _clean(x, 200)}
    out: list[dict[str, Any]] = []; seen: set[tuple[str, str]] = set()
    for entity in data.get("entities") or []:
        if not isinstance(entity, dict): continue
        name = _clean(entity.get("name"), 200); etype = _clean(entity.get("type"), 100) or "Entity"
        if not name: continue
        name_norm = _norm(name); type_norm = _norm(etype)
        if type_norm in {"author", "person author", "person/author", "creator", "social/creator"} and name_norm in author_norms: etype = "Channel/Uploader"
        elif type_norm in {"author", "person author", "person/author", "creator", "social/creator"} and (name_norm in commenter_norms or name.startswith("@")): etype = "Commenter"
        key = (_norm(etype), name_norm)
        if key not in seen: seen.add(key); out.append({**entity, "type": etype, "name": name})
    for author in authors:
        name = _clean(author, 200)
        if not name or _norm(name) in commenter_norms or name.startswith("@"): continue
        key = (_norm("Channel/Uploader"), _norm(name))
        if key not in seen: seen.add(key); out.append({"type": "Channel/Uploader", "name": name})
    data["entities"] = out
    facts = data.setdefault("key_facts", [])
    facts[:] = [row for row in facts if not (_norm(row.get("label")) in {"author", "person author", "person/author", "creator"} and (_norm(row.get("value")) in commenter_norms or str(row.get("value") or "").startswith("@")) and _norm(row.get("value")) not in author_norms)]


def _unwrap_link(url: str) -> tuple[str, str | None]:
    parsed = urlparse(url)
    if _youtube_host((parsed.hostname or "").casefold()) and parsed.path.rstrip("/") == "/redirect":
        qs = parse_qs(parsed.query)
        for key in ("q", "url"):
            value = (qs.get(key) or [None])[0]
            if value:
                dest = str(value).strip(); dest_parsed = urlparse(dest)
                if dest_parsed.scheme in {"http", "https"} and dest_parsed.hostname: return dest, (qs.get("event") or [None])[0]
    return url, None


def _canonical_youtube_video(url: str) -> str:
    parsed = urlparse(url); host = (parsed.hostname or "").casefold()
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
        if video_id: return f"https://www.youtube.com/watch?v={video_id}"
    if _youtube_host(host) and parsed.path == "/watch":
        video_id = (parse_qs(parsed.query).get("v") or [None])[0]
        if video_id: return f"https://www.youtube.com/watch?v={video_id}"
    return url


def _label_cleanup(label: Any, destination: str) -> str:
    text = _clean(label, 320) or _host(destination) or destination
    if markdown := re.fullmatch(r"\[([^\]]+)\]\([^)]+\)", text): text = markdown.group(1)
    if re.fullmatch(r"https?://\S+", text, re.I) or text.casefold() in {"visit", "www.youtube.com"}: text = _host(destination) or text
    cleaned = re.sub(r"^(?:\d{1,2}:)?\d{1,2}:\d{2}\s+", "", text).strip(); cleaned = re.sub(r"\s+[0-9][0-9,.]*[KMB]?\s+views\b.*$", "", cleaned, flags=re.I).strip(); cleaned = re.sub(r"\s+Live Playlist.*$", "", cleaned, flags=re.I).strip(); cleaned = re.sub(r"\s+Mix\s*\([0-9+]+\).*$", "", cleaned, flags=re.I).strip()
    return cleaned or text or _host(destination) or destination


def _resource_tokens(data: dict[str, Any]) -> set[str]:
    text = " ".join([str((data.get("identity") or {}).get("title") or ""), " ".join(str(x) for x in (data.get("tags") or [])), str(((data.get("sections") or {}).get("media") or {}).get("creator") or "")])
    return {token for token in _norm(text).split() if len(token) >= 4 and token not in VIDEO_GENERIC_WORDS}


def _link_role(url: str, label: str, wrapper_event: str | None, data: dict[str, Any]) -> tuple[str | None, float]:
    parsed = urlparse(url); host = (parsed.hostname or "").casefold()
    if host in {"accounts.google.com", "support.google.com"}: return None, 0.0
    if host in SOCIAL_HOSTS: return "social", 0.72
    if _youtube_host(host):
        if parsed.path.startswith("/@") or parsed.path.startswith("/channel/") or parsed.path.startswith("/c/"):
            return "channel", 0.90 if any(parsed.path.endswith(f"/{t}") for t in ("about", "videos", "featured", "playlists", "community", "shorts")) else 0.96
        if parsed.path == "/playlist" or "list" in parse_qs(parsed.query): return "playlist", 0.72
        if parsed.path == "/watch" or host == "youtu.be":
            if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", label.strip()): return None, 0.0
            matched = _resource_tokens(data) & set(_norm(label).split())
            return ("related_video", min(0.88, 0.48 + 0.08 * min(len(matched), 5))) if matched else (None, 0.0)
        return None, 0.0
    if wrapper_event in {"video_description", "endscreen"}: return "description_link", 0.92
    if wrapper_event: return "external", 0.60
    return ("external", 0.55) if host else (None, 0.0)


def _curate_video_links(data: dict[str, Any]) -> None:
    raw_links = list((data.get("evidence_archive") or {}).get("links") or []) + list((data.get("links") or {}).get("important") or [])
    candidates: list[dict[str, Any]] = []; seen: set[str] = set(); role_counts: Counter[str] = Counter()
    for raw in raw_links:
        if not isinstance(raw, dict): continue
        original_url = str(raw.get("url") or "").strip()
        if not original_url: continue
        destination, event = _unwrap_link(original_url); destination = _canonical_youtube_video(destination); parsed = urlparse(destination)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or destination.casefold() in seen: continue
        label = _label_cleanup(raw.get("label"), destination); role, score = _link_role(destination, label, event, data)
        if not role: continue
        if role == "channel" and label.casefold() in {"about", "videos", "featured", "community", "playlists", "shorts"}:
            creator = _clean(((data.get("sections") or {}).get("media") or {}).get("creator"), 200)
            if creator: label = f"{creator} ({label.capitalize()})"
        if role == "playlist" and not (_resource_tokens(data) & set(_norm(label).split())): continue
        if event == "video_description": score += 0.05
        candidates.append({"label": label, "url": destination, "relationship": role, "curation_role": role, "curation_score": round(min(1.0, score), 2), "source_context": _clean(raw.get("source_context"), 160), "unwrapped_from": original_url if destination != original_url else None}); seen.add(destination.casefold())
    priority = {"channel": 0, "description_link": 1, "social": 2, "playlist": 3, "related_video": 4, "external": 5}
    candidates.sort(key=lambda row: (priority.get(str(row.get("curation_role")), 9), -float(row.get("curation_score") or 0.0), str(row.get("label") or "").casefold()))
    out: list[dict[str, Any]] = []; caps = {"channel": 2, "description_link": 4, "social": 3, "playlist": 2, "related_video": 4, "external": 2}
    for row in candidates:
        role = str(row.get("curation_role") or "external")
        if role_counts[role] >= caps.get(role, 2): continue
        role_counts[role] += 1; out.append(row)
        if len(out) >= 12: break
    if out: data.setdefault("links", {})["important"] = out


__all__ = [name for name in globals() if not name.startswith("__")]
