from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from video_resource import _canonical_youtube_video, _clean, _clock_seconds, _norm, _unwrap_link, _youtube_host
from video_precision import _set_fact

DESCRIPTION_VERSION = 1
SECTION_NAMES = {
    "chapters": "chapters", "timestamps": "chapters", "sponsors": "sponsors", "sponsor": "sponsors",
    "sponsor discounts": "sponsor_discounts", "discounts": "sponsor_discounts", "with guests": "guests",
    "guests": "guests", "guest judges": "guests", "resources": "resources", "links": "links",
    "socials": "socials", "social": "socials", "credits": "credits", "tools": "resources",
}
COVERAGE_NOISE = {
    "overview", "history", "watch history", "feature", "season", "episode", "menu", "navigation",
    "search", "shopping", "up next", "recommended", "recommendations",
}
PLATFORM_HELP_HOSTS = {"support.google.com", "accounts.google.com"}
ROLE_PRIORITY: dict[str, int] = {
    "challenge": 0, "game": 1, "store": 2, "livestream": 3, "charity": 4, "channel": 5,
    "description_link": 6, "sponsor_offer": 7, "sponsor": 8, "guest": 9, "social": 10,
    "playlist": 11, "related_video": 12, "external": 13,
}
ROLE_CAPS: dict[str, int] = {
    "challenge": 2, "game": 2, "store": 2, "livestream": 2, "charity": 2, "channel": 1,
    "description_link": 4, "sponsor_offer": 2, "sponsor": 3, "guest": 2, "social": 2,
    "playlist": 1, "related_video": 2, "external": 1,
}
URL_RE = re.compile(r"https?://[^\s<>()\[\]{}]+", re.I)
CLOCK_RE = re.compile(r"(?<!\d)(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+?)(?=(?:\s+\d{1,2}:\d{2}(?::\d{2})?\s+)|$)")


def _page_url(data: dict[str, Any], acquired: Any) -> str:
    return str(getattr(acquired, "final_url", "") or (data.get("fetch") or {}).get("final_url") or (data.get("input") or {}).get("url") or "")


def _raw_description(player: dict[str, Any] | None) -> str:
    if not isinstance(player, dict):
        return ""
    details = player.get("videoDetails")
    if isinstance(details, dict) and isinstance(details.get("shortDescription"), str):
        return details["shortDescription"].replace("\r\n", "\n").replace("\r", "\n").strip()
    micro = ((player.get("microformat") or {}).get("playerMicroformatRenderer") or {})
    if isinstance(micro, dict):
        desc = micro.get("description")
        if isinstance(desc, str):
            return desc.replace("\r\n", "\n").replace("\r", "\n").strip()
        if isinstance(desc, dict):
            if isinstance(desc.get("simpleText"), str):
                return desc["simpleText"].replace("\r\n", "\n").replace("\r", "\n").strip()
            runs = desc.get("runs")
            if isinstance(runs, list):
                return "".join(str(x.get("text") or "") for x in runs if isinstance(x, dict)).strip()
    return ""


def _section_header(line: str) -> str | None:
    raw = line.strip()
    if not raw or "http://" in raw.casefold() or "https://" in raw.casefold():
        return None
    raw = raw.strip("*_#- ").rstrip(":").strip()
    norm = _norm(raw)
    if norm in SECTION_NAMES:
        return SECTION_NAMES[norm]
    if 1 <= len(raw.split()) <= 5 and any(ch.isalpha() for ch in raw):
        letters = [ch for ch in raw if ch.isalpha()]
        if letters and sum(ch.isupper() for ch in letters) / len(letters) >= 0.88:
            return norm.replace(" ", "_")
    return None


def _description_sections(raw: str) -> tuple[list[str], dict[str, list[str]]]:
    preamble: list[str] = []
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for original in raw.splitlines():
        line = original.strip()
        if not line:
            continue
        header = _section_header(line)
        if header:
            current = header
            sections.setdefault(current, [])
            continue
        if current:
            sections.setdefault(current, []).append(line)
        else:
            preamble.append(line)
    return preamble, sections


def _strip_url_punctuation(url: str) -> str:
    return url.rstrip(".,);]}>\"'")


def _canonical_description_url(url: str) -> str:
    destination, _event = _unwrap_link(_strip_url_punctuation(url))
    parsed = urlparse(destination)
    host = (parsed.hostname or "").casefold()
    if _youtube_host(host) and parsed.path.startswith("/live/"):
        video_id = parsed.path.split("/live/", 1)[1].split("/", 1)[0]
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
    return _canonical_youtube_video(destination)


def _link_role(label: str, section: str | None, url: str) -> tuple[str, float]:
    norm = _norm(label)
    host = (urlparse(url).hostname or "").casefold()
    if host in {"facebook.com", "www.facebook.com", "instagram.com", "www.instagram.com", "twitter.com", "www.twitter.com", "x.com", "www.x.com", "tiktok.com", "www.tiktok.com"}:
        return "social", 0.78
    if section == "sponsors":
        return "sponsor", 0.74
    if section == "sponsor_discounts":
        return "sponsor_offer", 0.76
    if section == "guests":
        return "guest", 0.70
    if "unesco" in norm or any(x in norm for x in ("charity", "fund", "donate", "benefit")):
        return "charity", 0.94
    if any(x in norm for x in ("accept the challenge", "enter the challenge", "join the challenge", "submit")):
        return "challenge", 1.0
    if any(x in norm for x in ("pre order", "preorder", "buy", "shop", "physical game")):
        return "store", 0.98
    if "play" in norm and "game" in norm:
        return "game", 0.99
    if any(x in norm for x in ("livestream", "live stream", "launch stream", "get started stream")):
        return "livestream", 0.97
    if section == "socials":
        return "social", 0.76
    return "description_link", 0.86


def _description_links(raw: str) -> list[dict[str, Any]]:
    preamble, sections = _description_sections(raw)
    lines_with_section: list[tuple[str | None, str]] = [(None, line) for line in preamble]
    for section, lines in sections.items():
        lines_with_section.extend((section, line) for line in lines)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for section, line in lines_with_section:
        matches = list(URL_RE.finditer(line))
        for index, match in enumerate(matches):
            url = _canonical_description_url(match.group(0))
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.hostname.casefold() in PLATFORM_HELP_HOSTS:
                continue
            label = (line[:match.start()] if index == 0 else line[matches[index - 1].end():match.start()]).strip(" \t:-–—*•")
            label = _clean(label, 140) or parsed.hostname
            if _norm(label) in {"http", "https"}:
                label = parsed.hostname
            role, score = _link_role(label, section, url)
            key = url.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "label": label, "url": url, "relationship": role, "curation_role": role,
                "description_section": section or "preamble", "curation_score": round(score, 2),
            })
    return out


def _narrative_summary(raw: str) -> str | None:
    preamble, _sections = _description_sections(raw)
    narrative: list[str] = []
    for line in preamble:
        matches = list(URL_RE.finditer(line))
        if matches:
            visible = URL_RE.sub("", line).strip(" \t:-–—*•")
            norm = _norm(visible)
            if (
                not visible
                or line[:matches[0].start()].rstrip().endswith(":")
                or any(norm.startswith(prefix) for prefix in (
                    "accept the challenge", "pre order", "preorder", "play the online", "get started livestream",
                    "get started live stream", "website", "instagram", "twitter", "facebook", "discord", "patreon",
                    "spotify", "check out", "visit", "follow", "subscribe",
                ))
            ):
                continue
            if len(visible) >= 60:
                narrative.append(visible)
            continue
        if re.fullmatch(r"(?:#[\w-]+\s*)+", line):
            continue
        narrative.append(line)
    text = _clean(" ".join(narrative), 1400)
    return text if text and len(text) >= 100 else None


def _chapter_url(page_url: str, seconds: int) -> str | None:
    canonical = _canonical_youtube_video(page_url)
    parsed = urlparse(canonical)
    if not (_youtube_host((parsed.hostname or "").casefold()) and parsed.path == "/watch"):
        return None
    video_id = (parse_qs(parsed.query).get("v") or [None])[0]
    if not video_id:
        return None
    base = f"https://www.youtube.com/watch?v={video_id}"
    return base if seconds <= 0 else f"{base}&t={seconds}s"


def _parse_chapters_from_description(raw: str, page_url: str) -> list[dict[str, Any]]:
    _preamble, sections = _description_sections(raw)
    lines = sections.get("chapters") or []
    if not lines:
        return []
    text = " ".join(lines)
    out: list[dict[str, Any]] = []
    seen_seconds: set[int] = set()
    for match in CLOCK_RE.finditer(text):
        display = match.group(1)
        seconds = _clock_seconds(display)
        title = _clean(match.group(2), 160)
        if seconds is None or not title or seconds in seen_seconds:
            continue
        title = re.sub(r"\s+", " ", title).strip(" -*•")
        if not title:
            continue
        seen_seconds.add(seconds)
        row: dict[str, Any] = {"title": title, "time": display, "seconds": seconds}
        url = _chapter_url(page_url, seconds)
        if url:
            row["url"] = url
        out.append(row)
    return out[:80]


def _parse_chapters_from_archive(data: dict[str, Any], page_url: str) -> list[dict[str, Any]]:
    groups = [x for x in (data.get("evidence_archive") or {}).get("grouped_values") or [] if isinstance(x, dict)]
    chapter_group = next((x for x in groups if _norm(x.get("label")).startswith("chapters view all")), None)
    if not chapter_group:
        return []
    labels = [_clean(x, 160) for x in (chapter_group.get("values") or [])]
    labels = [x for x in labels if x and _norm(x) not in {"transcript", "view all"}]
    time_map: dict[str, str] = {}
    for group in groups:
        label = _clean(group.get("label"), 160)
        if not label:
            continue
        for value in group.get("values") or []:
            clock = _clean(value, 30)
            if clock and _clock_seconds(clock) is not None:
                time_map[_norm(label)] = clock
                break
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for label in labels:
        clock = time_map.get(_norm(label))
        seconds = _clock_seconds(clock) if clock else None
        if seconds is None or seconds in seen:
            continue
        seen.add(seconds)
        row: dict[str, Any] = {"title": label, "time": clock, "seconds": seconds}
        url = _chapter_url(page_url, seconds)
        if url:
            row["url"] = url
        out.append(row)
    return out[:80]


def _promote_chapters(data: dict[str, Any], raw: str, page_url: str) -> list[dict[str, Any]]:
    chapters = _parse_chapters_from_description(raw, page_url) or _parse_chapters_from_archive(data, page_url)
    resource = data.setdefault("sections", {}).setdefault("resource_details", {})
    current = resource.get("chapters")
    if isinstance(current, str) and _norm(current) in {"view all", "transcript", "show transcript"}:
        resource.pop("chapters", None)
    if chapters:
        resource["chapters"] = chapters
        data.setdefault("sections", {}).setdefault("video_structure", {})["chapters"] = chapters
        _set_fact(data.setdefault("key_facts", []), "Chapters", str(len(chapters)))
    return chapters


__all__ = [name for name in globals() if not name.startswith("__")]
