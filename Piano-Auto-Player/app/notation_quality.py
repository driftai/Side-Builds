from __future__ import annotations

import html
import re


_DECIMAL = re.compile(r"[-+]?\d+\.\d+")
_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")
_SVG_COMMAND = re.compile(r"(?:^|(?<=[\s\d.,+-]))[MmLlHhVvCcSsQqTtAaZz](?=[\s\d.,+-]|$)")
_HTML_TAG = re.compile(r"<\s*/?\s*(?:svg|path|script|style|div|span|html|body|main|section|article)\b", re.I)
_URLISH = re.compile(r"(?:https?://|www\.|schema\.org|xmlns(?:=|:))", re.I)
_CODEISH = re.compile(r"\b(?:function|const|let|var|return|document|window|webpack|nextjs|__next)\b", re.I)
_CSSISH = re.compile(r"(?:[.#][A-Za-z_-][\w-]*\s*\{|\b(?:fill|stroke|viewbox|d)\s*[:=])", re.I)
_JSONISH = re.compile(r"(?:\\[\"'\\]|\\u[0-9a-f]{4}|[\"']\w{2,}[\"']\s*:|\{\s*[\"']\w+)", re.I)
_SENTENCE_PUNCT = re.compile(r"[.,;:?]")
_ALPHA_WORD = re.compile(r"\b[A-Za-z]{3,}\b")

# These are intentionally website/legal/product words rather than generic English
# vocabulary. Several hits in one candidate is a high-confidence sign that a
# provider returned page chrome, serialized locale strings, or a privacy notice.
_WEB_PROSE_TERMS = {
    "account", "application", "company", "cookies", "copyright", "description",
    "device", "google", "individual", "information", "machine", "metadata",
    "notifications", "personal", "privacy", "products", "registration", "service",
    "services", "sign", "terms", "website", "your", "purposes", "requests",
    "marketing", "analytics", "agreement", "store", "policy", "user", "users",
}


def _prose_reason(candidate: str) -> str:
    words = [word.lower() for word in _ALPHA_WORD.findall(candidate)]
    if not words:
        return ""
    tokens = re.findall(r"\S+", candidate)
    punctuation = len(_SENTENCE_PUNCT.findall(candidate))
    term_hits = sum(1 for word in words if word in _WEB_PROSE_TERMS)

    # Serialized Next.js/localization payloads often contain escaped quotes plus
    # long readable English strings. Treat that as page data before note scoring.
    json_hits = len(_JSONISH.findall(candidate))
    if len(candidate) >= 120 and json_hits >= 3 and len(words) >= 8:
        return "serialized webpage/JSON data"

    if len(candidate) >= 160 and term_hits >= 5:
        return "website/privacy prose"

    # Normal piano sheets can contain compact runs such as `asdfgh` or many
    # repeated letter groups, so punctuation is required before classifying generic
    # English-looking tokens as prose.
    long_words = sum(len(word) >= 4 for word in words)
    if len(tokens) >= 18 and punctuation >= 3 and long_words >= 10:
        if long_words / max(len(tokens), 1) >= 0.30:
            return "natural-language prose"

    # A paragraph may have very little punctuation after HTML/JSON normalization.
    # Multiple common web terms still make it unsafe as notation.
    if len(words) >= 25 and term_hits >= 3 and len(candidate) >= 240:
        return "website prose"
    return ""


def sheet_contamination_reason(text: str) -> str:
    """Return a high-confidence reason when *text* is not piano notation.

    Roblox/Virtual-Piano notation legitimately uses every ASCII letter and digit,
    so raw character allow-lists are not sufficient. This guard rejects structural
    signatures of markup, JSON, SVG, code, and natural-language webpage content
    while deliberately allowing compact letter runs, chords, rests, and bars.
    """
    candidate = html.unescape(str(text or "")).strip()
    if not candidate:
        return ""

    if _HTML_TAG.search(candidate):
        return "HTML/SVG markup"
    if _URLISH.search(candidate) and len(candidate) > 24:
        return "webpage/URL data"
    if _CODEISH.search(candidate) and any(token in candidate for token in ("=", "{", "}", ";")):
        return "JavaScript/code data"
    if _CSSISH.search(candidate) and any(token in candidate for token in ("{", "}", ":", '=\"', "='")):
        return "CSS/SVG attribute data"

    decimals = len(_DECIMAL.findall(candidate))
    numbers = len(_NUMBER.findall(candidate))
    svg_commands = len(_SVG_COMMAND.findall(candidate))
    if decimals >= 3 and numbers >= 10 and svg_commands >= 3:
        return "SVG path coordinate data"
    if decimals >= 8 and numbers >= 16:
        return "decimal coordinate/data payload"

    compact = re.sub(r"\s+", "", candidate)
    if len(compact) >= 80 and re.match(r"^[Mm][-+]?\d", compact) and compact[-1:] in {"Z", "z"}:
        if numbers >= 10 and svg_commands >= 2:
            return "SVG path coordinate data"

    return _prose_reason(candidate)
