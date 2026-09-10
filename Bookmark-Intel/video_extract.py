from __future__ import annotations

import json
import re
from html import unescape
from typing import Any

from bs4 import BeautifulSoup

APP_CHROME_SECTIONS = {"menu", "navigation", "nav", "search", "account", "sign in", "signin", "header", "footer", "create", "notifications", "settings"}
VIDEO_GENERIC_WORDS = {"video", "music", "official", "youtube", "netflix", "the", "and", "with", "from", "this", "that", "your", "house", "watch", "full", "live"}
SOCIAL_HOSTS = {"facebook.com", "www.facebook.com", "instagram.com", "www.instagram.com", "twitter.com", "www.twitter.com", "x.com", "www.x.com", "tiktok.com", "www.tiktok.com"}
TAG_NOISE = {"amp", "video", "videos", "entertainment"}


def _clean(value: Any, limit: int = 1800) -> str | None:
    if value is None or isinstance(value, bool): return None
    text = re.sub(r"\s+", " ", unescape(str(value))).strip()
    if not text: return None
    text = text.replace("… ...more", "…").replace("... ...more", "...")
    return text[:limit - 1].rstrip() + "…" if len(text) > limit else text


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _host(url: str) -> str:
    from urllib.parse import urlparse
    return (urlparse(str(url or "")).hostname or "").casefold().rstrip(".")


def _youtube_host(host: str) -> bool:
    return host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}


def _jsonld_video_objects(soup: BeautifulSoup) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    def walk(node: Any) -> None:
        if isinstance(node, dict):
            raw_type = node.get("@type")
            types = {raw_type} if isinstance(raw_type, str) else set(raw_type or []) if isinstance(raw_type, list) else set()
            if "VideoObject" in types: out.append(node)
            graph = node.get("@graph")
            if isinstance(graph, list):
                for child in graph: walk(child)
        elif isinstance(node, list):
            for child in node: walk(child)
    for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        raw = script.string or script.get_text("", strip=False)
        if not raw: continue
        try: walk(json.loads(raw))
        except Exception: continue
    return out


def _best_video_object(objects: list[dict[str, Any]], title: str) -> dict[str, Any] | None:
    if not objects: return None
    title_norm = _norm(title); scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, obj in enumerate(objects):
        name = _norm(obj.get("name") or obj.get("headline")); score = 0
        if title_norm and name == title_norm: score += 10
        elif title_norm and name and (title_norm in name or name in title_norm): score += 6
        score += sum(1 for key in ("description", "duration", "uploadDate", "interactionStatistic") if obj.get(key))
        scored.append((score, -index, obj))
    scored.sort(reverse=True, key=lambda row: (row[0], row[1]))
    return scored[0][2]


def _clock_seconds(value: str) -> int | None:
    parts = value.split(":")
    if len(parts) not in {2, 3} or not all(part.isdigit() for part in parts): return None
    nums = [int(x) for x in parts]
    if len(nums) == 2:
        minutes, seconds = nums
        return minutes * 60 + seconds if seconds < 60 else None
    hours, minutes, seconds = nums
    return hours * 3600 + minutes * 60 + seconds if minutes < 60 and seconds < 60 else None


def _iso_duration_seconds(raw: Any) -> int | None:
    if raw is None: return None
    if isinstance(raw, (int, float)): return int(round(raw))
    text = str(raw).strip()
    if text.isdigit(): return int(text)
    clock = _clock_seconds(text)
    if clock is not None: return clock
    match = re.fullmatch(r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?", text.upper())
    if not match: return None
    total = int(match.group("days") or 0) * 86400 + int(match.group("hours") or 0) * 3600 + int(match.group("minutes") or 0) * 60 + float(match.group("seconds") or 0)
    return int(round(total))


def _duration_display(seconds: int) -> str:
    seconds = max(0, int(seconds)); hours, rem = divmod(seconds, 3600); minutes, secs = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _visible_player_duration(soup: BeautifulSoup, structured_seconds: int | None) -> tuple[str | None, int | None]:
    if structured_seconds is None: return None, None
    text = soup.get_text(" ", strip=True)
    player_match = re.search(r"(?:0:)?00\s*/\s*((?:\d{1,2}:)?\d{1,2}:\d{2})", text)
    if player_match:
        raw = player_match.group(1); sec = _clock_seconds(raw)
        if sec is not None: return raw, sec
    elem = soup.find(class_=re.compile(r"ytp-time-duration|player-duration|vjs-duration-display", re.I))
    if elem:
        raw = elem.get_text(strip=True); sec = _clock_seconds(raw)
        if sec is not None: return raw, sec
    candidates: list[tuple[int, str, int]] = []
    for raw in re.findall(r"(?<!\d)(?:\d{1,2}:)?\d{1,2}:\d{2}(?!\d)", text):
        sec = _clock_seconds(raw)
        if sec is not None and abs(sec - structured_seconds) <= 3: candidates.append((abs(sec - structured_seconds), raw, sec))
    if not candidates: return None, None
    candidates.sort(key=lambda row: (row[0], row[2])); _, raw, sec = candidates[0]
    return raw, sec


def _parse_count(value: Any) -> tuple[int | None, str | None, bool]:
    text = _clean(value, 80)
    if not text: return None, None, False
    compact = text.replace(",", "").strip(); match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*([KMB])?", compact, re.I)
    if not match:
        digits = re.sub(r"[^0-9]", "", compact)
        if digits:
            number = int(digits); return number, f"{number:,}", False
        return None, text, False
    number = float(match.group(1)); suffix = (match.group(2) or "").upper(); multiplier = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[suffix]
    integer = int(round(number * multiplier)); approximate = bool(suffix or "." in match.group(1))
    return integer, text if approximate else f"{integer:,}", approximate


def _interaction_type(stat: dict[str, Any]) -> str:
    raw = stat.get("interactionType")
    if isinstance(raw, dict): raw = raw.get("@type") or raw.get("name") or raw.get("url")
    return _norm(raw)


def _engagement_from_video_object(video: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not video: return out
    stats = video.get("interactionStatistic") or []
    if isinstance(stats, dict): stats = [stats]
    for stat in stats if isinstance(stats, list) else []:
        if not isinstance(stat, dict): continue
        count, display, approximate = _parse_count(stat.get("userInteractionCount") or stat.get("interactionCount"))
        if count is None: continue
        kind = _interaction_type(stat); target = None
        if "watchaction" in kind or "view" in kind: target = "views"
        elif "likeaction" in kind or "like" in kind: target = "likes"
        elif "commentaction" in kind or "comment" in kind: target = "comments"
        if target: out[target] = {"count": count, "display": display or f"{count:,}", "approximate": approximate, "source": "structured"}
    if video.get("commentCount") not in (None, "") and "comments" not in out:
        count, display, approximate = _parse_count(video.get("commentCount"))
        if count is not None: out["comments"] = {"count": count, "display": display or f"{count:,}", "approximate": approximate, "source": "structured"}
    return out


def _first_visible_count(text: str, pattern: str) -> tuple[int | None, str | None, bool]:
    match = re.search(pattern, text, re.I)
    return _parse_count(match.group(1)) if match else (None, None, False)


def _augment_engagement_from_page(soup: BeautifulSoup, engagement: dict[str, dict[str, Any]]) -> None:
    text = soup.get_text(" ", strip=True)
    if "views" not in engagement:
        parsed = [_parse_count(x) for x in re.findall(r"([0-9][0-9,.]*(?:\.[0-9]+)?\s*[KMB]?)\s+views\b", text, re.I)]
        parsed = [x for x in parsed if x[0] is not None]
        if parsed:
            count, display, approximate = max(parsed, key=lambda row: int(row[0] or 0)); engagement["views"] = {"count": count, "display": display, "approximate": approximate, "source": "visible"}
    if "comments" not in engagement:
        count, display, approximate = _first_visible_count(text, r"([0-9][0-9,.]*(?:\.[0-9]+)?\s*[KMB]?)\s+comments\b")
        if count is not None: engagement["comments"] = {"count": count, "display": display, "approximate": approximate, "source": "visible"}
    count, display, approximate = _first_visible_count(text, r"([0-9][0-9,.]*(?:\.[0-9]+)?\s*[KMB]?)\s+subscribers\b")
    if count is not None: engagement["channel_subscribers"] = {"count": count, "display": display, "approximate": approximate, "source": "visible"}
    if "likes" not in engagement:
        for element in soup.find_all(attrs={"aria-label": True}):
            label = str(element.get("aria-label") or "")
            if "like" not in label.casefold() or "dislike" in label.casefold(): continue
            match = re.search(r"([0-9][0-9,.]*(?:\.[0-9]+)?\s*[KMB]?)", label, re.I)
            if match:
                count, display, approximate = _parse_count(match.group(1))
                if count is not None:
                    engagement["likes"] = {"count": count, "display": display, "approximate": approximate, "source": "visible_attribute"}; break
    if "likes" not in engagement:
        match = re.search(r"subscribers.{0,120}?([0-9]+(?:\.[0-9]+)?\s*[KMB])\s+Share\b", text, re.I)
        if match:
            count, display, approximate = _parse_count(match.group(1))
            if count is not None: engagement["likes"] = {"count": count, "display": display, "approximate": approximate, "source": "visible_context"}


def _description_candidate(video: dict[str, Any] | None, soup: BeautifulSoup) -> str | None:
    candidates: list[str] = []
    if video and video.get("description"):
        cleaned = _clean(video.get("description"), 5000)
        if cleaned: candidates.append(cleaned)
    for attrs in ({"name": "description"}, {"property": "og:description"}, {"itemprop": "description"}):
        meta = soup.find("meta", attrs=attrs)
        if meta and meta.get("content"):
            cleaned = _clean(meta.get("content"), 5000)
            if cleaned: candidates.append(cleaned)
    if not candidates: return None
    candidates.sort(key=len, reverse=True); text = candidates[0]
    lyrics = re.search(r"\bLyrics\b", text, re.I)
    if lyrics and lyrics.start() >= 120: text = text[:lyrics.start()].rstrip(" :-")
    text = re.sub(r"\s*(?:\.\.\.|…)\s*(?:\.\.\.)?more\b.*$", "", text, flags=re.I)
    return _clean(text, 1600)


__all__ = [name for name in globals() if not name.startswith("__")]
