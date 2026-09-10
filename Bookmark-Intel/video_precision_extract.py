from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from video_resource import _clean, _clock_seconds, _duration_display, _norm

PRECISION_VERSION = 2
AUTHOR_TYPES = {"author", "person author", "person/author", "creator", "social creator", "social/creator"}
COVERAGE_NOISE = {"menu", "navigation", "nav", "search", "account", "sign in", "signin", "header", "footer", "create", "notifications", "settings", "feature", "season", "episode", "up next", "recommended", "recommendations", "shopping"}
TAG_NOISE = {"amp", "sharing", "camera-phone", "video-phone", "free", "upload", "uploads", "people-blogs", "people", "blogs", "entertainment", "youtube", "youtu-be", "share", "subscribe", "subscribed", "download"}
LINK_GENERIC = {"video", "music", "official", "cover", "piano", "roblox", "anime", "netflix", "youtube", "channel", "upload", "uploads", "people", "blogs", "the", "and", "with", "from", "for", "this", "that", "your", "house", "live"}
TITLE_TAG_ALLOW = {"roblox", "piano", "cover", "music", "anime"}
SUMMARY_CHROME = ("if playback doesn't begin shortly", "videos you watch may be added", "you're signed out", "copy link info shopping", "share include playlist", "an error occurred while retrieving sharing information", "tap to unmute", "subscribe subscribed")


def _page_url(data: dict[str, Any], acquired: Any) -> str:
    return str(getattr(acquired, "final_url", "") or (data.get("fetch") or {}).get("final_url") or (data.get("input") or {}).get("url") or "")


def _balanced_json_after(text: str, marker: str) -> dict[str, Any] | None:
    start = text.find(marker)
    if start < 0: return None
    brace = text.find("{", start + len(marker))
    if brace < 0: return None
    depth = 0; in_string = False; escape = False
    for idx in range(brace, len(text)):
        ch = text[idx]
        if in_string:
            if escape: escape = False
            elif ch == "\\": escape = True
            elif ch == '"': in_string = False
            continue
        if ch == '"': in_string = True
        elif ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try: value = json.loads(text[brace:idx + 1])
                except Exception: return None
                return value if isinstance(value, dict) else None
    return None


def _youtube_state(html: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    player = next((x for x in (_balanced_json_after(html, m) for m in ("ytInitialPlayerResponse =", "ytInitialPlayerResponse=", '"ytInitialPlayerResponse":')) if x), None)
    initial = next((x for x in (_balanced_json_after(html, m) for m in ("ytInitialData =", "ytInitialData=", '"ytInitialData":')) if x), None)
    return player, initial


def _text_value(value: Any) -> str | None:
    if isinstance(value, str): return _clean(value, 500)
    if not isinstance(value, dict): return None
    simple = _clean(value.get("simpleText"), 500)
    if simple: return simple
    runs = value.get("runs")
    if isinstance(runs, list): return _clean("".join(str(x.get("text") or "") for x in runs if isinstance(x, dict)), 500)
    return None


def _walk(node: Any, max_nodes: int = 40000):
    stack = [node]; seen = 0
    while stack and seen < max_nodes:
        current = stack.pop(); seen += 1; yield current
        if isinstance(current, dict): stack.extend(reversed(list(current.values())))
        elif isinstance(current, list): stack.extend(reversed(current))


def _find_count(initial: Any, noun: str) -> str | None:
    pattern = re.compile(rf"([0-9][0-9,.]*(?:\.[0-9]+)?\s*[KMB]?)\s+{re.escape(noun)}\b", re.I)
    for current in _walk(initial):
        values = [current] if isinstance(current, str) else []
        if isinstance(current, dict): values.extend(current.get(k) for k in ("accessibilityText", "label", "text", "simpleText"))
        for raw in values:
            if isinstance(raw, str) and (match := pattern.search(raw)): return match.group(1)
    return None


def _find_subscribers(initial: Any) -> str | None:
    for current in _walk(initial):
        if not isinstance(current, dict) or "subscriberCountText" not in current: continue
        text = _text_value(current.get("subscriberCountText"))
        if text and (match := re.search(r"([0-9][0-9,.]*(?:\.[0-9]+)?\s*[KMB]?)\s+subscribers", text, re.I)): return match.group(1)
    return None


def _player_fields(player: dict[str, Any] | None) -> dict[str, Any]:
    if not player: return {}
    details = player.get("videoDetails") if isinstance(player.get("videoDetails"), dict) else {}
    micro = ((player.get("microformat") or {}).get("playerMicroformatRenderer") or {})
    if not isinstance(micro, dict): micro = {}
    out: dict[str, Any] = {}
    for key, raw in (("title", details.get("title") or micro.get("title")), ("creator", details.get("author") or micro.get("ownerChannelName")), ("description", details.get("shortDescription") or micro.get("description")), ("views", details.get("viewCount") or micro.get("viewCount")), ("category", micro.get("category")), ("upload_date", micro.get("uploadDate") or micro.get("publishDate")), ("channel_id", details.get("channelId") or micro.get("externalChannelId"))):
        value = _text_value(raw) if isinstance(raw, dict) else _clean(raw, 5000)
        if value: out[key] = value
    try:
        if details.get("lengthSeconds") not in (None, ""): out["duration_seconds"] = int(str(details["lengthSeconds"]))
    except (TypeError, ValueError): pass
    if isinstance(details.get("keywords"), list): out["keywords"] = [x for x in (_clean(v, 120) for v in details["keywords"]) if x]
    return out


def _count(value: Any) -> tuple[int | None, str | None, bool]:
    text = _clean(value, 80)
    if not text: return None, None, False
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*([KMB])?", text.replace(",", ""), re.I)
    if not match: return None, text, False
    base = float(match.group(1)); suffix = (match.group(2) or "").upper()
    number = int(round(base * {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[suffix]))
    approximate = bool(suffix or "." in match.group(1))
    return number, text if approximate else f"{number:,}", approximate


def _set_fact(facts: list[dict[str, Any]], label: str, value: Any) -> None:
    text = _clean(value, 500)
    if not text: return
    for row in facts:
        if isinstance(row, dict) and _norm(row.get("label")) == _norm(label): row.update(label=label, value=text); return
    facts.append({"label": label, "value": text})


def _remove_facts(facts: list[dict[str, Any]], labels: set[str]) -> None:
    targets = {_norm(x) for x in labels}
    facts[:] = [x for x in facts if not isinstance(x, dict) or _norm(x.get("label")) not in targets]


def _bad_summary(value: Any, title: str) -> bool:
    text = _clean(value, 2200) or ""
    if any(marker in text.casefold() for marker in SUMMARY_CHROME): return True
    title_norm = _norm(title)
    return bool(title_norm and _norm(text).count(title_norm) >= 2)


def _promote_player_state(data: dict[str, Any], soup: BeautifulSoup, fields: dict[str, Any], counts: dict[str, str]) -> None:
    sections = data.setdefault("sections", {}); media = sections.setdefault("media", {}); resource = sections.setdefault("resource_details", {}); facts = data.setdefault("key_facts", [])
    title = _clean((data.get("identity") or {}).get("title"), 500) or ""
    creator = _clean(fields.get("creator"), 200) or _clean(media.get("creator"), 200)
    if creator:
        media.update(creator=creator, channel=creator, uploader=creator); resource.update(authors=[creator], channel_name=creator, uploader=creator)
        _remove_facts(facts, {"Author"}); _set_fact(facts, "Channel / Uploader", creator)
    if (upload_date := _clean(fields.get("upload_date"), 100)) and not media.get("upload_date"):
        media["upload_date"] = resource["upload_date"] = upload_date; _set_fact(facts, "Upload Date", upload_date)
    seconds = fields.get("duration_seconds")
    if isinstance(seconds, int) and seconds >= 0 and not media.get("duration_seconds"):
        display = _duration_display(seconds); media.update(duration=display, duration_seconds=seconds, duration_iso=f"PT{seconds}S"); resource.update(duration=display, duration_seconds=seconds, duration_iso=f"PT{seconds}S")
        match = re.search(r"(?:0:)?00\s*/\s*((?:\d{1,2}:)?\d{1,2}:\d{2})", soup.get_text(" ", strip=True))
        if match and (visible_seconds := _clock_seconds(match.group(1))) is not None:
            visible = match.group(1); delta = visible_seconds - seconds; media.update(visible_player_duration=visible, duration_display_delta_seconds=delta)
            if abs(delta) <= 2 and delta: media["duration_timing_note"] = "Structured duration and visible player duration differ by <=2s; treated as player/display rounding."
            elif abs(delta) > 2: media["duration_timing_note"] = f"Material disagreement between structured duration ({display}) and visible player duration ({visible})."
        _set_fact(facts, "Duration", display)
    if (category := _clean(fields.get("category"), 120)) and not resource.get("platform_category"):
        media["platform_category"] = resource["platform_category"] = category; _remove_facts(facts, {"Genre"}); _set_fact(facts, "YouTube Category", category)
    engagement = media.get("engagement") if isinstance(media.get("engagement"), dict) else {}
    if "views" not in engagement and fields.get("views"):
        number, display, approximate = _count(fields["views"])
        if number is not None:
            engagement["views"] = display or f"{number:,}"; resource.update(views_count=number, views_display=engagement["views"], views_approximate=approximate); _set_fact(facts, "Views", engagement["views"])
    for key, label in (("likes", "Likes"), ("comments", "Comments"), ("channel_subscribers", "Channel Subscribers")):
        if key in engagement or not counts.get(key): continue
        number, display, approximate = _count(counts[key])
        if number is None: continue
        engagement[key] = display or f"{number:,}"; resource[f"{key}_count"] = number; resource[f"{key}_display"] = engagement[key]; resource[f"{key}_approximate"] = approximate; _set_fact(facts, label, engagement[key])
    if engagement: media["engagement"] = engagement
    description = _clean(fields.get("description"), 5000); current = _clean(data.get("summary"), 2200)
    if description:
        description = re.sub(r"\s*(?:\.\.\.|…)\s*(?:\.\.\.)?more\b.*$", "", description, flags=re.I)
        if (lyrics := re.search(r"\bLyrics\b", description, re.I)) and lyrics.start() >= 80: description = description[:lyrics.start()].rstrip(" :-")
        description = _clean(description, 1600)
        if description and (not current or _bad_summary(current, title) or current.endswith(("...", "…")) or len(description) >= len(current) + 50): data["summary"] = description


def _creator_norms(data: dict[str, Any], fields: dict[str, Any]) -> set[str]:
    media = ((data.get("sections") or {}).get("media") or {}); resource = ((data.get("sections") or {}).get("resource_details") or {})
    values: list[Any] = [media.get("creator"), media.get("channel"), media.get("uploader"), resource.get("channel_name"), resource.get("uploader"), fields.get("creator")]
    authors = resource.get("authors"); values.extend(authors if isinstance(authors, list) else [authors] if authors else [])
    return {_norm(v) for v in values if _clean(v, 200)}


def _clean_entities(data: dict[str, Any], fields: dict[str, Any]) -> None:
    allowed = _creator_norms(data, fields); out: list[dict[str, Any]] = []; seen: set[tuple[str, str]] = set()
    for row in data.get("entities") or []:
        if not isinstance(row, dict): continue
        name = _clean(row.get("name"), 200); etype = _clean(row.get("type"), 100) or "Entity"
        if not name: continue
        if _norm(etype) in AUTHOR_TYPES and _norm(name) not in allowed: continue
        if _norm(etype) in AUTHOR_TYPES and _norm(name) in allowed: etype = "Channel/Uploader"
        key = (_norm(etype), _norm(name))
        if key not in seen: seen.add(key); out.append({**row, "type": etype, "name": name})
    data["entities"] = out


__all__ = [name for name in globals() if not name.startswith("__")]
