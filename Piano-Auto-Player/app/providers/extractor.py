import html
import re
import string
from html.parser import HTMLParser
from urllib.parse import urljoin

from ..sheet_validation import sheet_contamination_reason, validate_sheet_text


PLAYABLE_NOTE_CHARS = set(string.ascii_letters + string.digits + "!@$%^*(")
KEY_CHARS = PLAYABLE_NOTE_CHARS | set("-_=[]{ }|\n\t")
BLOCK_TAGS = {"pre", "textarea", "code", "p", "div", "section", "article"}


class PageCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[list[str]] = []
        self._active_blocks: list[int] = []
        self.links: list[dict[str, str]] = []
        self._link_stack: list[int] = []
        self._h1_depth = 0
        self.h1_parts: list[str] = []
        self.all_parts: list[str] = []
        self.code_blocks: list[list[str]] = []
        self._code_stack: list[int] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_dict = dict(attrs)
        if tag in BLOCK_TAGS:
            self.blocks.append([])
            self._active_blocks.append(len(self.blocks) - 1)
        if tag == "code":
            self.code_blocks.append([])
            self._code_stack.append(len(self.code_blocks) - 1)
        if tag == "a":
            self.links.append({"href": attrs_dict.get("href", ""), "text": ""})
            self._link_stack.append(len(self.links) - 1)
        if tag == "h1":
            self._h1_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in BLOCK_TAGS and self._active_blocks:
            self._active_blocks.pop()
        if tag == "code" and self._code_stack:
            self._code_stack.pop()
        if tag == "a" and self._link_stack:
            self._link_stack.pop()
        if tag == "h1" and self._h1_depth:
            self._h1_depth -= 1

    def handle_data(self, data: str) -> None:
        if not data:
            return
        self.all_parts.append(data)
        for block_index in self._active_blocks:
            self.blocks[block_index].append(data)
        for code_index in self._code_stack:
            self.code_blocks[code_index].append(data)
        if self._link_stack:
            self.links[self._link_stack[-1]]["text"] += data
        if self._h1_depth:
            self.h1_parts.append(data)

    def visible_text(self) -> str:
        return " ".join(" ".join(self.all_parts).split())


def normalize_sheet(text: str) -> str:
    text = html.unescape(text).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def count_sheet_notes(text: str) -> int:
    return sum(char in PLAYABLE_NOTE_CHARS for char in normalize_sheet(text))


def count_sheet_tokens(text: str) -> int:
    """Count playable notation tokens without expanding chord members.

    RobloxPianoSheet publishes a `playable tokens` total, which is a better
    extraction sanity check than raw character count for chord-heavy sheets.
    """
    sheet = normalize_sheet(text)
    count = 0
    i = 0
    while i < len(sheet):
        char = sheet[i]
        if char in "[{":
            close = "]" if char == "[" else "}"
            end = sheet.find(close, i + 1)
            if end != -1:
                inner = sheet[i + 1:end]
                if any(c in PLAYABLE_NOTE_CHARS for c in inner):
                    count += 1
                i = end + 1
                continue
        if char in PLAYABLE_NOTE_CHARS or char in "-_=|":
            count += 1
        i += 1
    return count


def score_sheet_candidate(text: str) -> float:
    candidate = normalize_sheet(text)
    if len(candidate) < 20 or sheet_contamination_reason(candidate):
        return -1.0
    valid = sum(1 for char in candidate if char in KEY_CHARS)
    ratio = valid / max(len(candidate), 1)
    if ratio < 0.88:
        return -1.0

    words = re.findall(r"[A-Za-z]{6,}", candidate)
    long_word_penalty = min(len(words) / max(len(candidate) / 40, 1), 0.95)
    notation_marks = candidate.count("[") + candidate.count("|") + candidate.count("-")
    notation_bonus = 1.0 + 0.05 * min(notation_marks, 20)
    return len(candidate) * (ratio ** 4) * (1.0 - long_word_penalty) * notation_bonus


def extract_sheet_metadata(page_html: str) -> dict[str, float | int]:
    collector = PageCollector()
    collector.feed(page_html)
    text = collector.visible_text()
    metadata: dict[str, float | int] = {}

    note_duration = re.search(r"([\d,]+)\s+notes\s+(\d+(?:\.\d+)?)s\b", text, re.I)
    if note_duration:
        metadata["note_count"] = int(note_duration.group(1).replace(",", ""))
        metadata["duration_seconds"] = float(note_duration.group(2))
    else:
        note_match = re.search(r"([\d,]+)\s+notes\b", text, re.I)
        if note_match:
            metadata["note_count"] = int(note_match.group(1).replace(",", ""))

    token_match = re.search(r"([\d,]+)\s+playable\s+tokens\b", text, re.I)
    if token_match:
        metadata["token_count"] = int(token_match.group(1).replace(",", ""))

    bpm_match = re.search(r"\b(\d{2,3})\s*BPM\b", text, re.I)
    if bpm_match:
        metadata["bpm"] = int(bpm_match.group(1))
    else:
        tempo_match = re.search(r"\bTEMPO\b\s+(\d{2,3})\b", text, re.I)
        if tempo_match:
            metadata["bpm"] = int(tempo_match.group(1))

    target_length = re.search(r"\bTARGET\s+LENGTH\b\s+(\d{1,2}):(\d{2})", text, re.I)
    if target_length and "duration_seconds" not in metadata:
        minutes, seconds = map(int, target_length.groups())
        metadata["duration_seconds"] = float(minutes * 60 + seconds)

    # Virtual Piano publishes a recommended play length such as 01:06. Use
    # that duration as a timing calibration source when BPM is not exposed.
    recommended = re.search(
        r"recommended\s+time\s+to\s+play(?:\s+this\s+music\s+sheet)?\s+is\s+(\d{1,2}):(\d{2})",
        text, re.I,
    )
    if recommended and "duration_seconds" not in metadata:
        minutes, seconds = map(int, recommended.groups())
        metadata["duration_seconds"] = float(minutes * 60 + seconds)

    about_minutes = re.search(r"\bAbout\s+(\d+(?:\.\d+)?)\s+minutes?\b", text, re.I)
    if about_minutes and "duration_seconds" not in metadata:
        metadata["duration_seconds"] = round(float(about_minutes.group(1)) * 60.0, 3)
    return metadata


def _candidate_score(
    text: str, expected_notes: int | None, expected_tokens: int | None = None, weight: float = 1.0
) -> float:
    score = score_sheet_candidate(text)
    if score <= 0:
        return score

    multiplier = 1.0
    if expected_notes:
        notes = count_sheet_notes(text)
        if notes <= 0:
            return -1.0
        error = abs(notes - expected_notes) / max(expected_notes, 1)
        if notes > expected_notes * 3 or notes < expected_notes * 0.25:
            multiplier *= 0.002
        else:
            multiplier *= 0.25 + (1.0 / (1.0 + error * 12.0)) * 2.75
            if error <= 0.03:
                score += expected_notes * 25

    if expected_tokens:
        tokens = count_sheet_tokens(text)
        if tokens <= 0:
            return -1.0
        error = abs(tokens - expected_tokens) / max(expected_tokens, 1)
        if tokens > expected_tokens * 2.5 or tokens < expected_tokens * 0.30:
            multiplier *= 0.01
        else:
            multiplier *= 0.40 + (1.0 / (1.0 + error * 8.0)) * 2.10
            if error <= 0.04:
                score += expected_tokens * 18

    return score * multiplier * weight


def extract_sheet_from_html(
    page_html: str, expected_notes: int | None = None, expected_tokens: int | None = None
) -> tuple[str, str, str]:
    collector = PageCollector()
    collector.feed(page_html)
    title = " ".join(part.strip() for part in collector.h1_parts if part.strip()).strip()
    artist = ""

    candidates: list[tuple[float, str]] = []

    def add_candidate(text: str, weight: float = 1.0) -> None:
        score = _candidate_score(text, expected_notes, expected_tokens, weight)
        if score > 0:
            candidates.append((score, text))

    for parts in collector.blocks:
        add_candidate(" ".join(part.strip() for part in parts if part.strip()))

    for match in re.finditer(r"(?:sheet|notation|notes|sheetData|sheet_data|script)[\"']?\s*[:=]\s*[\"']([^\"']{20,})", page_html, re.I):
        add_candidate(match.group(1).replace("\\n", "\n").replace("\\t", "\t"), 1.25)

    # Modern sites commonly serialize the notation inside JSON/JS.
    for match in re.finditer(r"[\"']((?:\\.|[^\"']){35,12000})[\"']", page_html):
        text = match.group(1).replace("\\n", "\n").replace("\\r", "").replace("\\t", "\t")
        text = text.replace("\\u005b", "[").replace("\\u005d", "]")
        if score_sheet_candidate(text) > 80:
            add_candidate(text)

    # VPsheet and similar pages repeat the actual notation in their <code>
    # performance-tip snippets. Combining those snippets gives us a clean
    # fallback when the client-rendered sheet payload is otherwise hard to find.
    code_snippets = []
    for parts in collector.code_blocks:
        text = normalize_sheet(" ".join(part.strip() for part in parts if part.strip()))
        if count_sheet_notes(text) >= 2 and score_sheet_candidate(text) > 0:
            code_snippets.append(text)
    if code_snippets:
        add_candidate("\n".join(dict.fromkeys(code_snippets)), 1.35)

    if not candidates:
        raise ValueError("Could not find a piano-letter sheet on that page.")

    candidates.sort(key=lambda item: item[0], reverse=True)
    sheet = normalize_sheet(candidates[0][1])
    validate_sheet_text(sheet)

    if expected_notes:
        notes = count_sheet_notes(sheet)
        if notes > expected_notes * 2 or notes < expected_notes * 0.40:
            raise ValueError(
                f"Sheet extraction failed validation: host says {expected_notes} notes, "
                f"but extracted data contains {notes}."
            )
    if expected_tokens:
        tokens = count_sheet_tokens(sheet)
        if tokens > expected_tokens * 1.8 or tokens < expected_tokens * 0.45:
            raise ValueError(
                f"Sheet extraction failed validation: host says {expected_tokens} playable tokens, "
                f"but extracted data contains {tokens}."
            )

    if title and sheet.lower().startswith(title.lower()) and len(sheet) > len(title) + 20:
        sheet = sheet[len(title):].lstrip(" :-")

    for link in collector.links:
        label = " ".join(link["text"].split())
        href = link["href"]
        if label and label != title and len(label) < 80 and "/artist" in href:
            artist = label
            break

    return title or "Imported sheet", artist, sheet


def extract_virtual_piano_sheet(page_html: str) -> tuple[str, str, str]:
    """Extract only the primary sheet from a VirtualPiano music-sheet page.

    Those pages also contain full notation for related songs farther down the
    document. The primary notation sits after the TEMPO header and before the
    rating section, so isolate that region before generic candidate scoring.
    """
    collector = PageCollector()
    collector.feed(page_html)
    visible = collector.visible_text()
    title = " ".join(part.strip() for part in collector.h1_parts if part.strip()).strip()
    artist = ""

    match = re.search(
        r"\bTEMPO\b\s+\d{2,3}\b(.*?)\bRate\s+This\s+Music\s+Sheet\b",
        visible, re.I | re.S,
    )
    if not match:
        return extract_sheet_from_html(page_html)

    candidate = match.group(1)
    candidate = re.sub(r"^\s*\d+\s*\(\d+\)\s*", "", candidate)
    candidate = normalize_sheet(candidate)
    if score_sheet_candidate(candidate) <= 0:
        return extract_sheet_from_html(page_html)

    for link in collector.links:
        label = " ".join(link["text"].split())
        href = link["href"]
        if label and label != title and len(label) < 80 and "/artist" in href:
            artist = label
            break
    return title or "Imported sheet", artist, candidate


def sheet_links_from_html(page_html: str, base_url: str) -> list[dict[str, str]]:
    collector = PageCollector()
    collector.feed(page_html)
    found: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in collector.links:
        href = link["href"]
        if "/sheets/" not in href:
            continue
        url = urljoin(base_url, href)
        if url in seen:
            continue
        seen.add(url)
        title = " ".join(link["text"].split())
        if not title:
            title = href.rstrip("/").split("/")[-1].replace("-", " ").title()
        found.append({"title": title, "artist": "", "url": url})

    for match in re.finditer(r"(?:https?://playpianosheets\.com)?(/sheets/[a-zA-Z0-9_-]+)", page_html):
        href = match.group(1)
        url = urljoin(base_url, href)
        if url in seen:
            continue
        seen.add(url)
        title = href.rstrip("/").split("/")[-1].replace("-", " ").replace("_", " ").title()
        found.append({"title": title, "artist": "", "url": url})

    return found
