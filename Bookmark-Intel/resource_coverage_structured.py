from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

from resource_coverage_base import *


def _structured_script_groups(soup: BeautifulSoup) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_grp(label: str, vals: list[str], source: str) -> None:
        clean_vals = _clean_container_concatenations(_uniq(vals))
        if not clean_vals or label in seen:
            return
        seen.add(label)
        groups.append({"label": label, "values": clean_vals[:MAX_GROUP_VALUES], "source": source})

    for label, payload in _script_payloads(soup):
        if not isinstance(payload, dict):
            continue
        studios: list[str] = []
        if isinstance(payload.get("productionCompany"), list):
            for org in payload["productionCompany"]:
                if isinstance(org, dict):
                    name = _flatten_entity_name(org.get("name") or org)
                    if name:
                        studios.append(name)
        if isinstance(payload.get("studios"), dict) and "edges" in payload["studios"]:
            for edge in payload["studios"]["edges"]:
                if isinstance(edge, dict):
                    name = _flatten_entity_name(edge.get("node", {}).get("name") or edge.get("node") or edge.get("name"))
                    if name:
                        studios.append(name)
        elif isinstance(payload.get("studios"), list):
            for item in payload["studios"]:
                name = _flatten_entity_name(item.get("name") if isinstance(item, dict) else item)
                if name:
                    studios.append(name)
        if studios:
            add_grp("Studios", studios, f"{label}.studios")

        start = _format_date_obj(payload.get("startDate") or payload.get("airedFrom") or payload.get("premiereDate") or payload.get("datePublished"))
        if start:
            add_grp("Start Date", [start], f"{label}.startDate")
        end = _format_date_obj(payload.get("endDate") or payload.get("airedTo"))
        if end:
            add_grp("End Date", [end], f"{label}.endDate")
        updated = _format_date_obj(payload.get("updatedAt") or payload.get("dateModified"))
        if updated:
            add_grp("Last Update", [updated], f"{label}.updatedAt")

        if payload.get("isAdult") is False or payload.get("adult") is False:
            add_grp("Adult", ["No"], f"{label}.isAdult")
        elif payload.get("isAdult") is True or payload.get("adult") is True:
            add_grp("Adult", ["Yes"], f"{label}.isAdult")

        title_obj = payload.get("title")
        if isinstance(title_obj, dict):
            if title_obj.get("romaji"):
                add_grp("Romaji", [str(title_obj["romaji"])], f"{label}.title.romaji")
            if title_obj.get("native"):
                add_grp("Native", [str(title_obj["native"])], f"{label}.title.native")
        if isinstance(payload.get("alternateName"), list):
            add_grp("Native", [str(x) for x in payload["alternateName"]], f"{label}.alternateName")

        if isinstance(payload.get("genre"), list):
            add_grp("Genres", [str(x) for x in payload["genre"]], f"{label}.genre")
        elif isinstance(payload.get("genres"), list):
            add_grp("Genres", [str(x) for x in payload["genres"]], f"{label}.genres")
        if isinstance(payload.get("tags"), list):
            tag_names = []
            for tag in payload["tags"]:
                name = _flatten_entity_name(tag.get("name") if isinstance(tag, dict) else tag)
                if name:
                    tag_names.append(name)
            if tag_names:
                add_grp("Tags", tag_names, f"{label}.tags")

        if payload.get("countryOfOrigin"):
            add_grp("Country", [str(payload["countryOfOrigin"])], f"{label}.countryOfOrigin")
        if payload.get("format"):
            add_grp("Format", [str(payload["format"])], f"{label}.format")
        if payload.get("episodes") or payload.get("numberOfEpisodes"):
            add_grp("Episodes", [str(payload.get("episodes") or payload.get("numberOfEpisodes"))], f"{label}.episodes")
        if payload.get("averageScore") or payload.get("meanScore"):
            score_val = payload.get("averageScore") or payload.get("meanScore")
            add_grp("Score", [f"{score_val}/100" if isinstance(score_val, (int, float)) and score_val <= 100 else str(score_val)], f"{label}.score")
        if payload.get("source"):
            add_grp("Source", [str(payload["source"]).capitalize()], f"{label}.source")
    return groups


def _grouped_values(soup: BeautifulSoup) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    candidates = soup.find_all(["dt", "th", "legend", "h2", "h3", "h4", "h5", "h6", "b", "strong", "span", "div"])
    for label_el in candidates:
        if label_el.find_parent(["script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form"]):
            continue
        if not _is_labelish(label_el):
            continue
        label = _clean(label_el.get_text(" ", strip=True), 90)
        if not label:
            continue
        values = [v for v in _following_group_values(label_el) if v.casefold() != label.casefold()]
        if not values:
            continue
        key = (_norm(label), tuple(v.casefold() for v in values[:20]))
        if key in seen:
            continue
        seen.add(key)
        groups.append({"label": label.rstrip(":").strip(), "values": values[:MAX_GROUP_VALUES], "source": "grouped_dom"})
        if len(groups) >= MAX_GROUPS:
            break
    for structured in _structured_script_groups(soup):
        label = structured["label"]
        norm_label = _norm(label)
        existing = next((g for g in groups if _norm(g["label"]) == norm_label), None)
        if existing and len(structured.get("values", [])) > len(existing.get("values", [])):
            existing["values"] = _clean_container_concatenations(_uniq(existing.get("values", []) + structured.get("values", [])))
        elif not existing:
            groups.append(structured)
    return groups[:MAX_GROUPS]


def _script_payloads(soup: BeautifulSoup) -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    decoder = json.JSONDecoder()
    seen_labels: set[str] = set()
    for idx, script in enumerate(soup.find_all("script")):
        raw = script.string or script.get_text("", strip=False)
        if not raw or len(raw) > 4_000_000:
            continue
        script_type = str(script.get("type") or "").casefold()
        script_id = str(script.get("id") or "")
        label = script_id or f"script[{idx}]"
        if "json" in script_type or script_id in SCRIPT_STATE_MARKERS:
            try:
                payload = json.loads(raw)
                if label not in seen_labels:
                    seen_labels.add(label)
                    out.append((label, payload))
                continue
            except Exception:
                pass
        matched_marker = False
        for marker in SCRIPT_STATE_MARKERS:
            pos = raw.find(marker)
            if pos < 0:
                continue
            tail = raw[pos + len(marker):]
            starts = [x for x in (tail.find("{"), tail.find("[")) if x >= 0]
            if not starts:
                continue
            try:
                payload, _ = decoder.raw_decode(tail[min(starts):].lstrip())
                if marker not in seen_labels:
                    seen_labels.add(marker)
                    out.append((marker, payload))
                matched_marker = True
                break
            except Exception:
                pass
        if matched_marker:
            continue
        for match in re.finditer(r"(?:window\.)?([a-zA-Z0-9_$]*(?:__[A-Z0-9_]+__|STATE|DATA|CONFIG))\s*=\s*", raw):
            var_name = match.group(1)
            if var_name in seen_labels:
                continue
            tail = raw[match.end():].lstrip()
            if tail.startswith(("{", "[")):
                try:
                    payload, _ = decoder.raw_decode(tail)
                    if isinstance(payload, (dict, list)):
                        seen_labels.add(var_name)
                        out.append((var_name, payload))
                except Exception:
                    pass
    return out


def _compact_item(value: Any) -> Any:
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return _clean(value, 500)
    if isinstance(value, dict):
        unwrapped = dict(value)
        node = unwrapped.pop("node", None)
        if isinstance(node, dict):
            for key, child in node.items():
                if key not in unwrapped or unwrapped[key] in (None, "", {}, []):
                    unwrapped[key] = child
        compact: dict[str, Any] = {}
        preferred = (
            "id", "name", "title", "label", "role", "type", "status", "number", "episode",
            "chapter", "date", "airDate", "releaseDate", "description", "summary", "url",
            "voiceActors", "isMain", "format", "year",
        )
        keys = [k for k in preferred if k in unwrapped] or list(unwrapped.keys())[:8]
        for key in keys[:10]:
            child = unwrapped.get(key)
            if key in {"voiceActors", "voice_actors", "actors", "cast"} and isinstance(child, list):
                actors = []
                for actor in child[:8]:
                    if isinstance(actor, dict):
                        name = _flatten_entity_name(actor.get("name") or actor.get("node", {}).get("name") or actor)
                        language = _clean(actor.get("languageV2") or actor.get("language") or actor.get("role"), 40)
                        if name and language:
                            actors.append(f"{name} ({language})")
                        elif name:
                            actors.append(name)
                    elif isinstance(actor, str):
                        cleaned = _clean(actor, 100)
                        if cleaned:
                            actors.append(cleaned)
                if actors:
                    compact[str(key)] = actors
            elif key in {"name", "title"} and isinstance(child, dict):
                flat = _flatten_entity_name(child)
                if flat:
                    compact[str(key)] = flat
            elif isinstance(child, (str, int, float)) and not isinstance(child, bool):
                compact[str(key)] = _clean(child, 500)
            elif isinstance(child, list) and len(child) <= 8 and all(isinstance(x, (str, int, float)) and not isinstance(x, bool) for x in child):
                compact[str(key)] = [_clean(x, 200) for x in child]
            elif isinstance(child, dict) and key in {"image", "coverImage", "bannerImage"}:
                for image_key in ("large", "medium", "url", "src", "original"):
                    if isinstance(child.get(image_key), str):
                        compact[str(key)] = child[image_key]
                        break
        return compact or None
    if isinstance(value, list):
        return [_compact_item(x) for x in value[:6]]
    return None


def _structured_collections(soup: BeautifulSoup) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    visited = 0

    def walk(value: Any, path: str, depth: int = 0) -> None:
        nonlocal visited
        if len(results) >= MAX_STRUCTURED_COLLECTIONS or visited >= 6000 or depth > 10:
            return
        visited += 1
        if isinstance(value, dict):
            for key, child in value.items():
                key_text = str(key)
                norm_key = re.sub(r"[^a-z0-9]+", "", key_text.casefold())
                child_path = f"{path}.{key_text}" if path else key_text
                if norm_key in NOISE_JSON_KEYS:
                    continue
                if isinstance(child, list) and len(child) >= 2:
                    marker = (child_path.casefold(), len(child))
                    if marker not in seen:
                        seen.add(marker)
                        sample = []
                        for item in child[:MAX_STRUCTURED_SAMPLE_ITEMS]:
                            compact = _compact_item(item)
                            if compact not in (None, "", {}, []):
                                sample.append(compact)
                        if sample:
                            results.append({"path": child_path, "kind": "list", "count": len(child), "sample": sample})
                elif isinstance(child, dict) and 2 <= len(child) <= 500:
                    marker = (child_path.casefold(), len(child))
                    if bool(re.search(r"[a-zA-Z]{3,}", key_text)) and marker not in seen and depth >= 1:
                        compact = _compact_item(child)
                        if compact:
                            seen.add(marker)
                            results.append({"path": child_path, "kind": "object", "count": len(child), "sample": compact})
                if isinstance(child, (dict, list)):
                    walk(child, child_path, depth + 1)
        elif isinstance(value, list):
            for idx, child in enumerate(value[:250]):
                if isinstance(child, (dict, list)):
                    walk(child, f"{path}[{idx}]", depth + 1)

    for label, payload in _script_payloads(soup):
        walk(payload, label)
        if len(results) >= MAX_STRUCTURED_COLLECTIONS:
            break
    return results[:MAX_STRUCTURED_COLLECTIONS]


__all__ = [name for name in globals() if not name.startswith("__")]
