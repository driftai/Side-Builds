from __future__ import annotations

import re
from collections import Counter
from typing import Any
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from video_resource_metadata import *


def _unwrap_link(url: str) -> tuple[str, str | None]:
    parsed = urlparse(url)
    if _youtube_host((parsed.hostname or "").casefold()) and parsed.path.rstrip("/") == "/redirect":
        qs = parse_qs(parsed.query)
        for key in ("q", "url"):
            value = (qs.get(key) or [None])[0]
            if value:
                destination = str(value).strip()
                destination_parsed = urlparse(destination)
                if destination_parsed.scheme in {"http", "https"} and destination_parsed.hostname:
                    return destination, (qs.get("event") or [None])[0]
    return url, None


def _canonical_youtube_video(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
    if _youtube_host(host) and parsed.path == "/watch":
        video_id = (parse_qs(parsed.query).get("v") or [None])[0]
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
    return url


def _label_cleanup(label: Any, destination: str) -> str:
    text = _clean(label, 320) or _host(destination) or destination
    markdown = re.fullmatch(r"\[([^\]]+)\]\([^)]+\)", text)
    if markdown:
        text = markdown.group(1)
    if re.fullmatch(r"https?://\S+", text, re.I) or text.casefold() in {"visit", "www.youtube.com"}:
        text = _host(destination) or text
    cleaned = re.sub(r"^(?:\d{1,2}:)?\d{1,2}:\d{2}\s+", "", text).strip()
    cleaned = re.sub(r"\s+[0-9][0-9,.]*[KMB]?\s+views\b.*$", "", cleaned, flags=re.I).strip()
    cleaned = re.sub(r"\s+Live Playlist.*$", "", cleaned, flags=re.I).strip()
    cleaned = re.sub(r"\s+Mix\s*\([0-9+]+\).*$", "", cleaned, flags=re.I).strip()
    return cleaned or text or _host(destination) or destination


def _resource_tokens(data: dict[str, Any]) -> set[str]:
    text = " ".join([
        str((data.get("identity") or {}).get("title") or ""),
        " ".join(str(x) for x in (data.get("tags") or [])),
        str(((data.get("sections") or {}).get("media") or {}).get("creator") or ""),
    ])
    return {token for token in _norm(text).split() if len(token) >= 4 and token not in VIDEO_GENERIC_WORDS}


def _link_role(url: str, label: str, wrapper_event: str | None, data: dict[str, Any]) -> tuple[str | None, float]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    if host in {"accounts.google.com", "support.google.com"}:
        return None, 0.0
    if host in SOCIAL_HOSTS:
        return "social", 0.72
    if _youtube_host(host):
        if parsed.path.startswith("/@") or parsed.path.startswith("/channel/") or parsed.path.startswith("/c/"):
            subtab = any(parsed.path.endswith(f"/{tab}") for tab in ("about", "videos", "featured", "playlists", "community", "shorts"))
            return "channel", 0.90 if subtab else 0.96
        if parsed.path == "/playlist" or "list" in parse_qs(parsed.query):
            return "playlist", 0.72
        if parsed.path == "/watch" or host == "youtu.be":
            if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", label.strip()):
                return None, 0.0
            matched = _resource_tokens(data) & set(_norm(label).split())
            if not matched:
                return None, 0.0
            return "related_video", min(0.88, 0.48 + 0.08 * min(len(matched), 5))
        return None, 0.0
    if wrapper_event in {"video_description", "endscreen"}:
        return "description_link", 0.92
    if wrapper_event:
        return "external", 0.60
    if host:
        return "external", 0.55
    return None, 0.0


def _curate_video_links(data: dict[str, Any]) -> None:
    raw_links: list[dict[str, Any]] = []
    raw_links.extend((data.get("evidence_archive") or {}).get("links") or [])
    raw_links.extend((data.get("links") or {}).get("important") or [])
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    role_counts: Counter[str] = Counter()
    for raw in raw_links:
        if not isinstance(raw, dict):
            continue
        original_url = str(raw.get("url") or "").strip()
        if not original_url:
            continue
        destination, event = _unwrap_link(original_url)
        destination = _canonical_youtube_video(destination)
        parsed = urlparse(destination)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            continue
        dedupe = destination.casefold()
        if dedupe in seen:
            continue
        label = _label_cleanup(raw.get("label"), destination)
        role, score = _link_role(destination, label, event, data)
        if not role:
            continue
        if role == "channel" and label.casefold() in {"about", "videos", "featured", "community", "playlists", "shorts"}:
            creator = _clean(((data.get("sections") or {}).get("media") or {}).get("creator"), 200)
            if creator:
                label = f"{creator} ({label.capitalize()})"
        if role == "playlist" and not (_resource_tokens(data) & set(_norm(label).split())):
            continue
        if event == "video_description":
            score += 0.05
        candidates.append({
            "label": label, "url": destination, "relationship": role, "curation_role": role,
            "curation_score": round(min(1.0, score), 2),
            "source_context": _clean(raw.get("source_context"), 160),
            "unwrapped_from": original_url if destination != original_url else None,
        })
        seen.add(dedupe)

    priority = {"channel": 0, "description_link": 1, "social": 2, "playlist": 3, "related_video": 4, "external": 5}
    candidates.sort(key=lambda row: (priority.get(str(row.get("curation_role")), 9), -float(row.get("curation_score") or 0.0), str(row.get("label") or "").casefold()))
    out: list[dict[str, Any]] = []
    caps = {"channel": 2, "description_link": 4, "social": 3, "playlist": 2, "related_video": 4, "external": 2}
    for row in candidates:
        role = str(row.get("curation_role") or "external")
        if role_counts[role] >= caps.get(role, 2):
            continue
        role_counts[role] += 1
        out.append(row)
        if len(out) >= 12:
            break
    if out:
        data.setdefault("links", {})["important"] = out


def _clean_video_tags(data: dict[str, Any]) -> None:
    title = _norm((data.get("identity") or {}).get("title"))
    summary = _norm(data.get("summary"))
    creator = _norm(((data.get("sections") or {}).get("media") or {}).get("creator"))
    corpus = f"{title} {summary} {creator}"
    corpus_tokens = set(corpus.split())
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in data.get("tags") or []:
        tag = re.sub(r"[^a-z0-9]+", "-", str(raw).casefold()).strip("-")
        if not tag or tag in TAG_NOISE or tag in seen:
            continue
        phrase = _norm(tag)
        tag_tokens = set(phrase.split())
        if tag.count("-") >= 2 and phrase not in corpus:
            continue
        if any(ch.isdigit() for ch in tag) and phrase not in corpus and not (tag_tokens & corpus_tokens):
            continue
        seen.add(tag)
        cleaned.append(tag)
    if "video" not in cleaned:
        cleaned.insert(0, "video")
    data["tags"] = cleaned[:20]
    data.setdefault("bookmark", {})["suggested_tags"] = list(data["tags"])


def _normalize_video_coverage(data: dict[str, Any]) -> None:
    coverage = data.get("resource_coverage")
    if not isinstance(coverage, dict):
        return
    semantic_detected = []
    for row in coverage.get("interactive_sections_detected") or []:
        if not isinstance(row, dict):
            continue
        label = _norm(row.get("label"))
        if label in APP_CHROME_SECTIONS or any(token in APP_CHROME_SECTIONS for token in label.split()):
            continue
        semantic_detected.append(row)
    semantic_labels = {_norm(row.get("label")) for row in semantic_detected}
    covered = [x for x in (coverage.get("covered_sections") or []) if _norm(x) in semantic_labels]
    missing = [x for x in (coverage.get("missing_sections") or []) if _norm(x) in semantic_labels]
    coverage["interactive_sections_detected"] = semantic_detected
    coverage["covered_sections"] = covered
    coverage["missing_sections"] = missing
    if semantic_detected:
        coverage["resource_coverage_score"] = round(len({_norm(x) for x in covered}) / len(semantic_labels), 2)
        coverage["needs_deepening"] = bool(missing)
    if not missing:
        coverage["needs_deepening"] = False


def finalize_video_resource(data: dict[str, Any], acquired: Any) -> dict[str, Any]:
    """Promote high-value video evidence without treating page chrome as resource facts."""
    kind = str((data.get("classification") or {}).get("kind") or "").casefold()
    media_type = str((((data.get("sections") or {}).get("resource_details") or {}).get("media_type") or "")).casefold()
    if kind != "video" and media_type != "video":
        return data
    soup = BeautifulSoup(str(getattr(acquired, "text", "") or ""), "html.parser")
    title = _clean((data.get("identity") or {}).get("title"), 500) or ""
    video = _best_video_object(_jsonld_video_objects(soup), title)
    commenters = _commenter_handles(soup)
    _promote_video_fields(data, video, soup, commenters)
    _fix_entities(data, soup, commenters)
    _curate_video_links(data)
    _clean_video_tags(data)
    _normalize_video_coverage(data)
    profile = data.setdefault("resource_profile", {})
    profile.setdefault("format", "video")
    profile["media_family"] = profile.get("media_family") or "Video"
    quality = data.setdefault("quality", {})
    recovered = set(str(x) for x in (quality.get("structured_fields_recovered") or []))
    recovered.update({"video_creator", "video_duration", "curated_video_links"})
    if (((data.get("sections") or {}).get("media") or {}).get("engagement")):
        recovered.add("video_engagement")
    quality["structured_fields_recovered"] = sorted(recovered)
    return data


__all__ = [name for name in globals() if not name.startswith("__")]
