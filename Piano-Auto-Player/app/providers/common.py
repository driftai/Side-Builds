import html
import re
from difflib import SequenceMatcher
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen


USER_AGENT = "Mozilla/5.0 PianoAutoPlayer/0.4.0 (+localhost personal sheet finder)"


def get_html(url: str, timeout: int = 10) -> tuple[str, str]:
    request = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-US,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml",
    })
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace"), response.geturl()


def get_bytes(url: str, timeout: int = 15, accept: str = "application/octet-stream,*/*") -> tuple[bytes, str]:
    request = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-US,en;q=0.8",
        "Accept": accept,
    })
    with urlopen(request, timeout=timeout) as response:
        return response.read(), response.geturl()


def query_tokens(query: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", query.lower())


def normalize_search_text(value: str) -> str:
    return " ".join(query_tokens(value))


def _fuzzy_token_hit(token: str, candidates: list[str]) -> float:
    if len(token) < 4:
        return 0.0
    best = 0.0
    for candidate in candidates:
        if abs(len(candidate) - len(token)) > 3:
            continue
        best = max(best, SequenceMatcher(None, token, candidate).ratio())
    return best if best >= 0.80 else 0.0


def score_match(query: str, title: str, artist: str = "") -> int:
    """Score a search result by closeness to the user's query.

    Exact words and phrases dominate. Fuzzy matching is intentionally limited to
    words of four or more characters so a short query token such as ``on`` does
    not match inside unrelated words such as ``normal``.
    """
    q_tokens = query_tokens(query)
    if not q_tokens:
        return 0

    q_norm = normalize_search_text(query)
    title_norm = normalize_search_text(title)
    artist_norm = normalize_search_text(artist)
    title_tokens = query_tokens(title)
    artist_tokens = query_tokens(artist)
    title_set = set(title_tokens)
    artist_set = set(artist_tokens)

    exact_title = sum(token in title_set for token in q_tokens)
    exact_artist = sum(token in artist_set for token in q_tokens)
    fuzzy_title = sum(bool(_fuzzy_token_hit(token, title_tokens)) for token in q_tokens if token not in title_set)
    fuzzy_artist = sum(
        bool(_fuzzy_token_hit(token, artist_tokens))
        for token in q_tokens
        if token not in title_set and token not in artist_set
    )

    if not (exact_title or exact_artist or fuzzy_title or fuzzy_artist):
        return 0

    score = exact_title * 140 + exact_artist * 75 + fuzzy_title * 35 + fuzzy_artist * 20
    all_title_tokens = all(token in title_set for token in q_tokens)
    all_combined_tokens = all(token in title_set or token in artist_set for token in q_tokens)

    if q_norm and title_norm == q_norm:
        score += 1600
    elif q_norm and title_norm.startswith(q_norm):
        score += 1200
    elif q_norm and q_norm in title_norm:
        score += 1000
    elif q_norm and q_norm in f"{title_norm} {artist_norm}".strip():
        score += 700

    if all_title_tokens:
        score += 650
    elif all_combined_tokens:
        score += 400

    # Prefer compact titles when two rows contain the same matching phrase.
    if title_norm and q_norm:
        score += int(SequenceMatcher(None, q_norm, title_norm).ratio() * 120)
        score -= min(80, max(0, len(title_tokens) - len(q_tokens)) * 4)

    return max(1, score)


def dedupe_rank(query: str, items: list[dict], limit: int = 12) -> list[dict]:
    best: dict[str, dict] = {}
    for item in items:
        url = str(item.get("url") or "")
        if not url:
            continue
        item = dict(item)
        item["score"] = score_match(query, str(item.get("title") or ""), str(item.get("artist") or ""))
        if item["score"] <= 0:
            continue
        current = best.get(url)
        if current is None or item["score"] > current.get("score", 0):
            best[url] = item
    ranked = sorted(best.values(), key=lambda row: (-row.get("score", 0), row.get("title", "").lower()))
    for item in ranked:
        item.pop("score", None)
    return ranked[:limit]


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str]] = []
        self._stack: list[int] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "a":
            attrs_dict = dict(attrs)
            self.links.append({"href": attrs_dict.get("href", ""), "text": ""})
            self._stack.append(len(self.links) - 1)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._stack:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        if self._stack:
            self.links[self._stack[-1]]["text"] += data


def links_matching(page_html: str, base_url: str, path_fragment: str) -> list[dict[str, str]]:
    parser = LinkCollector()
    parser.feed(page_html)
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in parser.links:
        href = html.unescape(link["href"])
        if path_fragment not in href:
            continue
        url = urljoin(base_url, href)
        if url in seen:
            continue
        seen.add(url)
        title = " ".join(link["text"].split()) or href.rstrip("/").split("/")[-1].replace("-", " ").title()
        items.append({"title": title, "artist": "", "url": url})
    return items


def search_url(base: str, query: str) -> str:
    return f"{base}?s={quote_plus(query)}"


NETWORK_ERRORS = (HTTPError, URLError, TimeoutError, OSError)
