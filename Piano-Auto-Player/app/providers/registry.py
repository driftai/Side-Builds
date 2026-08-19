from concurrent.futures import ThreadPoolExecutor, as_completed

from .common import score_match
from ..media_reference import MediaReferenceResolver
from ..sheet_validation import validate_sheet_text
from ..performance_notation import performance_to_sheet
from .dynshii import DynShiiProvider
from .gamepianosheets import GamePianoSheetsProvider
from .musicboxmaniacs import MusicBoxManiacsProvider
from .myvirtualpiano import MyVirtualPianoSheetsProvider
from .playpianosheets import PlayPianoSheetsProvider
from .onlinesequencer import OnlineSequencerProvider
from .pianoletternotes import PianoLetterNotesProvider
from .robloxpianosheet import RobloxPianoSheetProvider
from .virtualpiano import VirtualPianoProvider
from .virtualpianosheet import VirtualPianoSheetProvider
from .vpsheet import VPSheetProvider
from .toonkeys import ToonKeysProvider


DEFAULT_INTERVAL_MS = {
    "playpianosheets": 115.0, "vpsheet": 115.0, "virtualpiano": 115.0,
    "myvirtualpiano": 115.0, "robloxpianosheet": 115.0, "virtualpianosheet": 115.0,
    "dynshii": 115.0, "gamepianosheets": 115.0, "pianoletternotes": 182.0,
}


class ProviderRegistry:
    def __init__(self) -> None:
        self.providers = [
            PlayPianoSheetsProvider(),
            VPSheetProvider(),
            VirtualPianoProvider(),
            MyVirtualPianoSheetsProvider(),
            RobloxPianoSheetProvider(),
            VirtualPianoSheetProvider(),
            DynShiiProvider(),
            GamePianoSheetsProvider(),
            PianoLetterNotesProvider(),
            MusicBoxManiacsProvider(),
            OnlineSequencerProvider(),
            ToonKeysProvider(),
        ]
        self.by_id = {provider.id: provider for provider in self.providers}

    def info(self) -> list[dict[str, str]]:
        return [{"id": p.id, "name": p.name} for p in self.providers]

    def search(self, query: str, selected: list[str] | None = None, per_provider: int = 8) -> dict:
        providers = [p for p in self.providers if not selected or p.id in selected]
        results: list[dict] = []
        errors: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=max(1, len(providers))) as executor:
            futures = {executor.submit(p.search, query, per_provider): p for p in providers}
            for future in as_completed(futures):
                provider = futures[future]
                try:
                    results.extend(future.result())
                except Exception as exc:
                    errors[provider.id] = str(exc)

        # Providers finish in arbitrary order. Re-rank their combined results so
        # the closest query match always appears first regardless of host.
        def rank_score(row: dict) -> int:
            relevance = score_match(query, str(row.get("title") or ""), str(row.get("artist") or ""))
            # Exact sequence/MIDI sources win a small fidelity tiebreaker without
            # allowing an unrelated MIDI title to outrank a clearly better match.
            return relevance + (80 if row.get("fidelity") == "midi" and relevance > 0 else 0)

        results.sort(key=lambda row: (
            -rank_score(row),
            str(row.get("title") or "").lower(),
            str(row.get("provider_name") or "").lower(),
        ))
        return {"results": results, "errors": errors, "providers": self.info()}


    def best_reference(self, query: str, artist: str = "") -> dict:
        value = " ".join(str(query or "").split()).strip()[:180]
        if len(value) < 2:
            return {"reference": None, "results": [], "queries": [], "resolved_title": value, "errors": {}}
        queries = MediaReferenceResolver.reference_queries(value, artist)
        combined_results: dict[str, dict] = {}
        all_errors: dict[str, str] = {}

        for q in queries[:4]:
            searched = self.search(q, None, per_provider=4)
            all_errors.update(searched.get("errors", {}))
            for row in searched.get("results", []):
                url = row.get("url") or row.get("title")
                if url and url not in combined_results:
                    combined_results[url] = dict(row)

        ranked = []
        for row in combined_results.values():
            base_score = max(score_match(q, str(row.get("title") or ""), str(row.get("artist") or "")) for q in queries)
            confidence, score = MediaReferenceResolver.reference_confidence(value, row, base_score, queries)
            item = dict(row)
            item["reference_confidence"] = confidence
            fidelity = str(item.get("fidelity") or "").lower()
            fidelity_boost = 180 if fidelity == "midi" else 60 if item.get("provider") in {"gamepianosheets", "virtualpianosheet", "playpianosheets", "vpsheet", "myvirtualpiano", "robloxpianosheet", "dynshii"} else 0
            item["reference_score"] = score + fidelity_boost
            ranked.append(item)

        ranked.sort(key=lambda row: (
            -1 if row.get("reference_confidence") == "exact" else -0.5 if row.get("reference_confidence") == "strong" else 0,
            -int(row.get("reference_score") or 0),
            0 if row.get("fidelity") == "midi" else 1,
            str(row.get("title") or "").lower(),
        ))

        reference = next((row for row in ranked if MediaReferenceResolver.acceptable_reference(
            str(row.get("reference_confidence") or "candidate"),
            int(row.get("reference_score") or 0), row
        )), None)

        return {
            "reference": reference,
            "results": ranked[:8],
            "queries": queries,
            "resolved_title": value,
            "skipped_audio": bool(reference),
            "errors": all_errors,
        }

    def fetch(self, url: str, provider_id: str = "") -> dict:
        provider = self.by_id.get(provider_id) if provider_id else None
        if provider is None:
            provider = next((item for item in self.providers if item.accepts(url)), None)
        if provider is None:
            raise ValueError("No configured provider recognizes that sheet URL.")
        result = provider.fetch(url)
        if result.get("performance") and not str(result.get("sheet") or "").strip():
            result["sheet"] = performance_to_sheet(result["performance"])
        if str(result.get("sheet") or "").strip():
            validate_sheet_text(str(result["sheet"]))
        # Every non-timed sheet receives an explicit timing baseline. This prevents
        # one imported host's 25 ms setting from leaking into the next host.
        if not result.get("performance") and not result.get("recommended_interval_ms"):
            result["recommended_interval_ms"] = DEFAULT_INTERVAL_MS.get(provider.id, 115.0)
        return result
