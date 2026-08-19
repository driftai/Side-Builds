import tempfile
import time
import unittest
from pathlib import Path

from app.library import SongLibrary
from app.parser import parse_sheet, summarize_sheet
from app.playback import PlaybackController, PlaybackOptions
from app.state import RuntimeState
from app.providers.common import dedupe_rank, score_match


class CoreTests(unittest.TestCase):
    def test_parser(self):
        events = parse_sheet("ab [Cd] -- {ef}|g")
        kinds = [event.kind for event in events]
        self.assertIn("chord", kinds)
        self.assertIn("fast", kinds)
        self.assertGreaterEqual(kinds.count("pause"), 2)
        self.assertEqual(summarize_sheet("abc [de] --")["notes"], 3)

    def test_recording_library(self):
        with tempfile.TemporaryDirectory() as directory:
            library = SongLibrary(Path(directory) / "songs.json")
            saved = library.save({
                "title": "Timing test",
                "performance": [
                    {"key": "a", "at_ms": 0, "duration_ms": 30},
                    {"key": "s", "at_ms": 125, "duration_ms": 40},
                ],
            })
            self.assertEqual(saved["kind"], "performance")
            self.assertEqual(len(saved["performance"]), 2)
            self.assertGreaterEqual(saved["duration_ms"], 165)

    def test_timed_dry_run(self):
        state = RuntimeState()
        controller = PlaybackController(state)
        controller.start_performance(
            [{"key": "a", "at_ms": 0, "duration_ms": 10}, {"key": "s", "at_ms": 20, "duration_ms": 10}],
            "dry",
            PlaybackOptions(dry_run=True, countdown_seconds=0, speed=4),
        )
        for _ in range(100):
            if state.status in {"complete", "error"}:
                break
            time.sleep(0.01)
        self.assertEqual(state.status, "complete")

    def test_search_ranking(self):
        rows = [
            {"title": "505 Arctic Monkeys Normal Hard", "url": "https://example/505"},
            {"title": "Titan", "url": "https://example/titan"},
            {"title": "Apple Seed Attack On Titan Hiroyuki Sawano", "url": "https://example/apple"},
            {"title": "Attack on Titan", "url": "https://example/aot"},
        ]
        result = dedupe_rank("attack on titan", rows)
        self.assertEqual(result[0]["title"], "Attack on Titan")
        self.assertEqual(result[1]["title"], "Apple Seed Attack On Titan Hiroyuki Sawano")
        self.assertNotIn("505 Arctic Monkeys Normal Hard", [row["title"] for row in result])

    def test_short_token_does_not_match_inside_word(self):
        self.assertEqual(score_match("attack on titan", "505 Arctic Monkeys Normal Hard"), 0)
        self.assertGreater(score_match("attack on titan", "Attack On Titan - Guren No Yumiya"), 0)

    def test_typo_tolerance_keeps_real_match(self):
        self.assertGreater(score_match("attak titan", "Attack on Titan"), 0)


if __name__ == "__main__":
    unittest.main()

# v0.2.2 import hardening tests
from app.providers.extractor import count_sheet_notes, extract_sheet_from_html, extract_sheet_metadata


class ImportValidationTests(unittest.TestCase):
    def test_parser_ignores_non_piano_punctuation(self):
        events = parse_sheet('/schema.org";@typ/vpshee')
        values = ''.join(event.value for event in events if event.kind == 'note')
        self.assertNotIn('/', values)
        self.assertNotIn('.', values)
        self.assertNotIn('"', values)
        self.assertIn('@', values)  # @ is a real black-key character

    def test_vpsheet_metadata_and_code_fallback(self):
        sheet_parts = [
            'S-S-f-D- a-a-S-S- f-D-a--',
            'sdfGH-f- G-D-f-S- D-a--H- f-G-D-f- D-S-s--',
            'DaSpaOPI DaSOPOIi O-OOOPaP Oo-YIO- YIa-IOa-',
            'OaS-SSS SOS-aaaI a-SSSSPS Sss---',
            'SSfDaaSS fDa-SSfD SS-aOa- SSfDaaSS- f-D-a-',
            'SSfDSaH- G--SSfD aaSSfDa- SSfDSSaO a-SSfDaS SfDa-SS fDSaS--',
            'HfGDfSDa--- HfGD fGf',
        ]
        self.assertEqual(count_sheet_notes('\n'.join(sheet_parts)), 179)
        html = '<html><body><h1>Attack On Titan</h1><div>120 BPM 179 notes 59.5s</div>'
        html += '<script type="application/ld+json">' + ('schema metadata words ' * 500) + '</script>'
        html += ''.join(f'<p>Tip <code>{part}</code></p>' for part in sheet_parts) + '</body></html>'
        meta = extract_sheet_metadata(html)
        self.assertEqual(meta['note_count'], 179)
        self.assertEqual(meta['bpm'], 120)
        self.assertAlmostEqual(meta['duration_seconds'], 59.5)
        _title, _artist, sheet = extract_sheet_from_html(html, expected_notes=179)
        self.assertEqual(count_sheet_notes(sheet), 179)

# v0.2.3 expressive timing / input-envelope tests
from app.keyboard_win import char_needs_shift, key_message_lparam
from app.parser import total_timing_units
from app.providers.extractor import extract_virtual_piano_sheet


class ExpressiveTimingTests(unittest.TestCase):
    def test_adjacent_notes_are_faster_than_spaced_notes(self):
        adjacent = total_timing_units("asdf")
        spaced = total_timing_units("a s d f")
        self.assertGreater(spaced, adjacent)

    def test_spaced_brackets_are_fast_sequence_not_chord(self):
        compact = parse_sheet("[asdf]")
        spaced = parse_sheet("[a s d f]")
        self.assertEqual([event.kind for event in compact], ["chord"])
        self.assertTrue(spaced)
        self.assertTrue(all(event.kind == "fast" for event in spaced))

    def test_paragraph_break_is_longer_than_space(self):
        short = total_timing_units("a b")
        paragraph = total_timing_units("a\n\nb")
        self.assertGreater(paragraph, short)

    def test_black_key_detection(self):
        self.assertTrue(char_needs_shift("A"))
        self.assertTrue(char_needs_shift("@"))
        self.assertFalse(char_needs_shift("a"))
        self.assertFalse(char_needs_shift("4"))

    def test_virtual_piano_primary_sheet_beats_related_song_blob(self):
        html = """<html><body><h1>Guren no Yumiya</h1>
        <a href='/artist/linked-horizon'>Linked Horizon</a>
        <div>TARGET LENGTH 01:06</div><div>TEMPO 120</div><div>0 (0)</div>
        <div>DDGg SSD DGg S|| J GH g G D g S</div>
        <div>Rate This Music Sheet:</div>
        <h2>Other Songs</h2><div>[toD] """ + ("asdf " * 500) + """</div>
        </body></html>"""
        title, artist, sheet = extract_virtual_piano_sheet(html)
        self.assertEqual(title, "Guren no Yumiya")
        self.assertEqual(artist, "Linked Horizon")
        self.assertIn("DDGg", sheet)
        self.assertLess(len(sheet), 200)

    def test_virtual_piano_target_length_and_tempo_metadata(self):
        html = "<div>TARGET LENGTH 01:06</div><div>TEMPO 120</div>"
        meta = extract_sheet_metadata(html)
        self.assertEqual(meta["duration_seconds"], 66.0)
        self.assertEqual(meta["bpm"], 120)


# v0.2.4 global-speed / routing tests
class RoutingAndSpeedTests(unittest.TestCase):
    def test_global_speed_scales_sheet_hold(self):
        event = parse_sheet("a b")[0]
        options = PlaybackOptions(interval_ms=200, note_hold_ms=18, adaptive_hold=True, gate_percent=58)
        hold_1x = PlaybackController._sheet_hold_ms(event, 1.0, options, 1.0)
        hold_2x = PlaybackController._sheet_hold_ms(event, 1.0, options, 2.0)
        self.assertLess(hold_2x, hold_1x)

    def test_global_speed_clamps_to_ui_range(self):
        self.assertEqual(PlaybackController._speed(PlaybackOptions(speed=9)), 3.0)
        self.assertEqual(PlaybackController._speed(PlaybackOptions(speed=0.01)), 0.25)

    def test_virtual_target_mode_is_supported(self):
        options = PlaybackOptions(input_mode="virtual_target", target_hwnd=1234)
        self.assertEqual(options.input_mode, "virtual_target")
        self.assertEqual(options.target_hwnd, 1234)

class BackgroundV2PortableTests(unittest.TestCase):
    def test_key_message_lparam_has_scan_and_release_bits(self):
        down = key_message_lparam(0x1E, False)
        up = key_message_lparam(0x1E, True)
        self.assertEqual((down >> 16) & 0xFF, 0x1E)
        self.assertEqual(down & 0xFFFF, 1)
        self.assertEqual((down >> 30) & 0b11, 0)
        self.assertEqual((up >> 30) & 0b11, 0b11)

    def test_legacy_route_is_not_the_new_default(self):
        options = PlaybackOptions(input_mode="foreground", target_hwnd=1234)
        self.assertNotEqual(options.input_mode, "background_legacy")



# v0.2.6 event seek tests
class EventSeekTests(unittest.TestCase):
    def test_start_event_is_one_based_and_clamped(self):
        self.assertEqual(PlaybackController._start_zero_index(1000, 1), 0)
        self.assertEqual(PlaybackController._start_zero_index(1000, 456), 455)
        self.assertEqual(PlaybackController._start_zero_index(1000, 5000), 999)

    def test_idle_seek_updates_visible_position(self):
        state = RuntimeState(total_events=1000)
        controller = PlaybackController(state)
        self.assertEqual(controller.seek(456), 456)
        self.assertEqual(state.current_index, 456)

    def test_sheet_can_start_from_later_event(self):
        state = RuntimeState()
        controller = PlaybackController(state)
        controller.start(
            "a b c d", "seek dry",
            PlaybackOptions(dry_run=True, countdown_seconds=0, interval_ms=2, start_event=3),
        )
        for _ in range(100):
            if state.status in {"complete", "error"}:
                break
            time.sleep(0.01)
        self.assertEqual(state.status, "complete")
        self.assertEqual(state.total_events, len(parse_sheet("a b c d")))


class CatalogExtractionTests(unittest.TestCase):
    def test_playable_token_counter_keeps_chords_as_one_token(self):
        from app.providers.extractor import count_sheet_tokens
        self.assertEqual(count_sheet_tokens("a [s d] -- {fgh} | j"), 7)

# v0.2.7 stop/resume, host-aware timing, and provider expansion tests
class V027BehaviorTests(unittest.TestCase):
    def test_vpsheet_grid_ignores_formatting_spaces(self):
        spaced = parse_sheet("S-S-f-D- a-a", "vpsheet")
        compact = parse_sheet("S-S-f-D-a-a", "vpsheet")
        self.assertEqual(spaced, compact)
        self.assertEqual(sum(event.kind == "pause" for event in spaced), 5)

    def test_grid_bracket_spaces_stay_a_chord(self):
        events = parse_sheet("[a s d]", "vpsheet")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, "chord")
        self.assertEqual(events[0].value, "asd")

    def test_grid_underscore_is_an_explicit_rest(self):
        events = parse_sheet("a _ b", "roblox_grid")
        self.assertEqual([event.kind for event in events], ["note", "pause", "note"])

    def test_stop_creates_resume_bookmark_and_clears_visible_event(self):
        state = RuntimeState(status="playing", current_index=66, total_events=451)
        controller = PlaybackController(state)
        controller._thread = type("FakeThread", (), {"is_alive": lambda self: True})()
        resume = controller.stop()
        self.assertEqual(resume, 66)
        controller._finish(451)
        self.assertEqual(state.status, "idle")
        self.assertEqual(state.current_index, 0)
        self.assertEqual(state.snapshot().get("resume_index"), 66)

    def test_natural_finish_clears_resume_bookmark(self):
        state = RuntimeState(status="playing", current_index=10, total_events=10)
        state.update(resume_index=7)
        controller = PlaybackController(state)
        controller._finish(10)
        self.assertEqual(state.status, "complete")
        self.assertEqual(state.current_index, 10)
        self.assertEqual(state.snapshot().get("resume_index"), 0)

    def test_new_provider_registry_has_expanded_hosts(self):
        from app.providers.registry import ProviderRegistry
        ids = {item["id"] for item in ProviderRegistry().info()}
        self.assertTrue({"robloxpianosheet", "virtualpianosheet", "dynshii"}.issubset(ids))

    def test_virtual_target_replaces_focus_pulse_option(self):
        options = PlaybackOptions(input_mode="virtual_target", target_hwnd=1234)
        self.assertEqual(options.input_mode, "virtual_target")

class VPSheetSustainTests(unittest.TestCase):
    def test_vpsheet_dash_marks_previous_note_for_sustain(self):
        events = parse_sheet("a--b", "vpsheet")
        self.assertEqual(events[0].kind, "note")
        self.assertEqual(events[0].hold_units, 2.0)
        self.assertEqual(events[1].kind, "pause")
        self.assertEqual(events[1].units, 2.0)

    def test_vpsheet_sustain_uses_longer_hold_than_plain_grid(self):
        sustained = parse_sheet("a-b", "vpsheet")[0]
        plain = parse_sheet("a-b", "roblox_grid")[0]
        options = PlaybackOptions(interval_ms=250, note_hold_ms=18, adaptive_hold=True, gate_percent=58)
        sustained_hold = PlaybackController._sheet_hold_ms(sustained, 2.0, options, 1.0)
        plain_hold = PlaybackController._sheet_hold_ms(plain, 2.0, options, 1.0)
        self.assertGreater(sustained_hold, plain_hold)
        self.assertGreater(sustained_hold, 300)


# v0.2.8 focus-isolation portability tests
class V029VirtualTargetTests(unittest.TestCase):
    def test_virtual_target_module_imports_portably(self):
        from app.virtual_target import VirtualTargetWindowsKeyboard
        self.assertTrue(callable(VirtualTargetWindowsKeyboard))

    def test_virtual_focus_sequence_does_not_require_foreground_api(self):
        from app.virtual_target import WM_ACTIVATE, WM_ACTIVATEAPP, WM_SETFOCUS, virtual_focus_messages
        sequence = virtual_focus_messages(222, 333)
        self.assertEqual([item[0] for item in sequence], [WM_ACTIVATEAPP, WM_ACTIVATE, WM_SETFOCUS])
        self.assertEqual(sequence[0][2], 333)
        self.assertEqual(sequence[-1][1], 222)

    def test_virtual_target_route_key_is_supported(self):
        options = PlaybackOptions(input_mode="virtual_target", target_hwnd=1234)
        self.assertEqual(options.input_mode, "virtual_target")


# v0.3.0 octave-letter provider / converter tests
class PianoLetterNotesTests(unittest.TestCase):
    def test_octave_staff_maps_vertical_notes_to_qwerty_chords(self):
        from app.providers.pianoletternotes import convert_letter_staff
        source = "RH:4|d---F---|\nLH:3|d-------|\nLH:2|----a---|"
        sheet, stats = convert_letter_staff(source)
        self.assertEqual(sheet, "[9y]---[6I]")
        self.assertEqual(stats["note_count"], 2)
        self.assertEqual(stats["chord_count"], 2)

    def test_uppercase_staff_note_maps_to_black_key(self):
        from app.providers.pianoletternotes import convert_letter_staff
        sheet, _stats = convert_letter_staff("RH:4|G---|")
        self.assertEqual(sheet, "O")

    def test_letter_grid_uses_grid_timing(self):
        events = parse_sheet("a---b", "letter_grid")
        self.assertEqual([event.kind for event in events], ["note", "pause", "note"])
        self.assertEqual(events[1].units, 3.0)

    def test_provider_registry_includes_piano_letter_notes(self):
        from app.providers.registry import ProviderRegistry
        ids = {item["id"] for item in ProviderRegistry().info()}
        self.assertIn("pianoletternotes", ids)

    def test_long_title_query_gets_broad_song_variant(self):
        from app.providers.pianoletternotes import PianoLetterNotesProvider
        variants = PianoLetterNotesProvider._query_variants(
            "Spider Man 1967 Theme – Bob Harris and Paul Francis Webster Spider-man"
        )
        self.assertIn("Spider Man 1967 Theme", variants)

    def test_letter_staff_extractor_finds_code_block(self):
        from app.providers.pianoletternotes import extract_letter_staff
        html = "<html><body><h1>The Amazing Spider-Man - Original Theme (1967) | Piano Letter Notes</h1>" \
               "<code>RH:4|d---f---|<br>LH:3|d-------|</code></body></html>"
        title, source = extract_letter_staff(html)
        self.assertEqual(title, "The Amazing Spider-Man - Original Theme (1967)")
        self.assertIn("RH:4|d---f---|", source)

    def test_blogger_missing_blank_lines_still_split_staff_blocks(self):
        from app.providers.pianoletternotes import convert_letter_staff
        source = "RH:4|d---f---|\nLH:3|d-------|\nRH:4|g---a---|\nLH:3|g-------|"
        sheet, stats = convert_letter_staff(source)
        self.assertEqual(stats["note_count"], 4)
        self.assertIn("[9y]", sheet)
        self.assertIn("[wo]", sheet)


# v0.3.1 Piano Letter Notes pacing/grouping corrections
class PianoLetterNotesV031Tests(unittest.TestCase):
    def test_letter_grid_dashes_are_the_gap_not_note_plus_gap(self):
        events = parse_sheet("a---b", "letter_grid")
        self.assertEqual([event.kind for event in events], ["note", "pause", "note"])
        self.assertEqual(events[0].units, 0.0)
        self.assertEqual(events[1].units, 3.0)
        self.assertEqual(total_timing_units("a---b", "letter_grid"), 3.0)

    def test_letter_grid_adjacent_notes_get_short_step_only(self):
        events = parse_sheet("ab", "letter_grid")
        self.assertEqual(events[0].units, 0.45)
        self.assertEqual(events[1].units, 0.0)

    def test_duplicate_staff_lane_starts_new_sequential_group(self):
        from app.providers.pianoletternotes import convert_letter_staff
        sheet, stats = convert_letter_staff("RH:4|d---|\nRH:4|f---|")
        self.assertEqual(stats["note_count"], 2)
        self.assertEqual(stats["chord_count"], 0)
        self.assertNotIn("[", sheet)

    def test_spiderman_opening_block_keeps_true_column_onsets(self):
        from app.providers.pianoletternotes import convert_letter_staff
        source = "RH:4|d---f-a---------G---f-d---|\nLH:3|d---------------d---------|\nLH:2|------------a-------------|"
        sheet, stats = convert_letter_staff(source)
        self.assertEqual(stats["note_count"], 7)
        self.assertEqual(stats["chord_count"], 2)
        # First D chord -> F is separated by exactly three dash units.
        events = parse_sheet(sheet, "letter_grid")
        self.assertEqual(events[0].kind, "chord")
        self.assertEqual(events[1].kind, "pause")
        self.assertEqual(events[1].units, 3.0)

    def test_letter_grid_can_hold_longer_than_plain_grid_without_changing_gate(self):
        event = parse_sheet("a-----b", "letter_grid")[0]
        letter_options = PlaybackOptions(interval_ms=182, note_hold_ms=18, adaptive_hold=True, gate_percent=58, timing_profile="letter_grid")
        plain_options = PlaybackOptions(interval_ms=182, note_hold_ms=18, adaptive_hold=True, gate_percent=58, timing_profile="roblox_grid")
        letter_hold = PlaybackController._sheet_hold_ms(event, 5.0, letter_options, 1.0)
        plain_hold = PlaybackController._sheet_hold_ms(event, 5.0, plain_options, 1.0)
        self.assertGreater(letter_hold, plain_hold)
        self.assertGreater(letter_hold, 400)

# v0.3.3 seek/playhead stability tests
class V033SeekStabilityTests(unittest.TestCase):
    def test_latest_seek_request_wins(self):
        state = RuntimeState(total_events=1000)
        controller = PlaybackController(state)
        controller._thread = type("FakeThread", (), {"is_alive": lambda self: True})()
        controller.seek(200)
        controller.seek(700)
        self.assertEqual(controller._consume_seek(1000), 699)
        self.assertEqual(state.current_index, 700)

    def test_performance_cleaner_preserves_chord_keys(self):
        cleaned = PlaybackController._clean_performance([
            {"key": "aS9", "at_ms": 0, "duration_ms": 125},
        ])
        self.assertEqual(cleaned[0]["key"], "aS9")

    def test_seek_cancels_current_note_before_new_position(self):
        import threading
        from unittest.mock import patch

        played = []
        note_started = threading.Event()

        class FakeKeyboard:
            def tap_char(self, char, hold_ms=18, modifier_lead_ms=6, modifier_tail_ms=2, cancel_check=None):
                played.append(char)
                note_started.set()
                deadline = time.monotonic() + 0.25
                while time.monotonic() < deadline:
                    if cancel_check and cancel_check():
                        return
                    time.sleep(0.002)
            def tap_chord(self, chars, *args, **kwargs):
                return self.tap_char(chars, cancel_check=kwargs.get("cancel_check"))

        state = RuntimeState()
        controller = PlaybackController(state)
        with patch("app.playback.IS_WINDOWS", True), patch("app.playback.WindowsKeyboard", FakeKeyboard), patch("app.playback.resolve_window", return_value=(1, "Roblox")):
            controller.start("abc", "seek cancellation", PlaybackOptions(countdown_seconds=0, auto_focus=False, interval_ms=10))
            self.assertTrue(note_started.wait(0.5))
            controller.seek(3)
            for _ in range(150):
                if state.status in {"complete", "error"}:
                    break
                time.sleep(0.01)
        self.assertEqual(state.status, "complete")
        self.assertEqual(played[0], "a")
        self.assertNotIn("b", played)
        self.assertEqual(played[-1], "c")
