from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin

from .extractor import PLAYABLE_NOTE_CHARS, count_sheet_tokens, normalize_sheet
from ..sheet_validation import validate_sheet_text


class _RobloxPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._button_depth = 0
        self._button_parts: list[str] = []
        self.buttons: list[str] = []
        self._link_depth = 0
        self._link_parts: list[str] = []
        self._link_href = ""
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_dict = dict(attrs)
        if tag == "button":
            self._button_depth += 1
            if self._button_depth == 1:
                self._button_parts = []
        elif tag == "a":
            self._link_depth += 1
            if self._link_depth == 1:
                self._link_parts = []
                self._link_href = attrs_dict.get("href", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "button" and self._button_depth:
            self._button_depth -= 1
            if self._button_depth == 0:
                self.buttons.append("".join(self._button_parts).strip())
        elif tag == "a" and self._link_depth:
            self._link_depth -= 1
            if self._link_depth == 0:
                self.links.append((self._link_href, "".join(self._link_parts).strip()))

    def handle_data(self, data: str) -> None:
        if self._button_depth:
            self._button_parts.append(data)
        if self._link_depth:
            self._link_parts.append(data)


def find_midi_download(page_html: str, base_url: str) -> str:
    parser = _RobloxPageParser()
    parser.feed(page_html)
    for href, label in parser.links:
        clean = " ".join(label.split()).lower()
        if href and ("download midi" in clean or ("midi" in clean and href.lower().split("?")[0].endswith((".mid", ".midi")))):
            return urljoin(base_url, href)
    for match in re.finditer(r'["\']([^"\']+\.(?:mid|midi)(?:\?[^"\']*)?)["\']', page_html, re.I):
        return urljoin(base_url, match.group(1))
    return ""


def _is_note_token(value: str) -> bool:
    token = "".join(value.split())
    if not token or len(token) > 80:
        return False
    if token in {"-", "_", "=", "|"}:
        return True
    if len(token) == 1:
        return token in PLAYABLE_NOTE_CHARS
    if token[0] in "[{" and token[-1] in "]}":
        inner = token[1:-1]
        return bool(inner) and all(char in PLAYABLE_NOTE_CHARS for char in inner)
    return False


def extract_button_notation(page_html: str, expected_tokens: int | None = None) -> str:
    """Extract only explicit playable-token buttons from current host pages.

    This intentionally ignores prose, scripts, locale JSON, and privacy content.
    If the page does not expose enough token buttons to represent the published
    sheet total, it fails instead of returning a partial or guessed song.
    """
    parser = _RobloxPageParser()
    parser.feed(page_html)
    tokens = ["".join(button.split()) for button in parser.buttons if _is_note_token(button)]
    if not tokens or (not expected_tokens and len(tokens) < 12):
        raise ValueError("The page did not expose enough verifiable playable-note buttons.")
    sheet = normalize_sheet(" ".join(tokens))
    validate_sheet_text(sheet)
    actual = count_sheet_tokens(sheet)
    if expected_tokens and (actual < expected_tokens * 0.80 or actual > expected_tokens * 1.20):
        raise ValueError(
            f"The host reports {expected_tokens} playable tokens but only {actual} verifiable tokens were exposed; refusing a partial sheet."
        )
    return sheet
