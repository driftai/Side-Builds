import unittest
from pathlib import Path

from app.parser import parse_sheet
from app.playback import PlaybackController, PlaybackOptions
from app.preview_timeline import build_performance_preview, build_sheet_preview


class V036InternalPreviewTests(unittest.TestCase):
    def test_sheet_preview_uses_same_grid_timing_and_global_speed(self):
        options = PlaybackOptions(
            interval_ms=100,
            note_hold_ms=18,
            adaptive_hold=False,
            speed=2,
            timing_profile="vpsheet",
        )
        preview = build_sheet_preview("a-b", options)
        self.assertEqual(preview["total_events"], 3)
        self.assertEqual([row["kind"] for row in preview["events"]], ["note", "pause", "note"])
        self.assertEqual([row["at_ms"] for row in preview["events"]], [0.0, 50.0, 100.0])
        self.assertEqual(preview["events"][1]["duration_ms"], 50.0)

    def test_sheet_preview_reuses_external_adaptive_hold_math(self):
        options = PlaybackOptions(interval_ms=180, note_hold_ms=18, adaptive_hold=True, gate_percent=58, speed=1.5)
        events = parse_sheet("a b")
        expected = PlaybackController._sheet_hold_ms(
            events[0], PlaybackController._gap_to_next_onset(events, 0), options, PlaybackController._speed(options)
        )
        preview = build_sheet_preview("a b", options)
        self.assertAlmostEqual(preview["events"][0]["duration_ms"], expected, places=3)

    def test_midi_preview_preserves_chord_and_gate_at_speed(self):
        options = PlaybackOptions(speed=2, gate_percent=58, timing_profile="midi")
        performance = [
            {"key": "as", "at_ms": 1000, "duration_ms": 800},
            {"key": "d", "at_ms": 1500, "duration_ms": 500},
        ]
        preview = build_performance_preview(performance, options)
        first, second = preview["events"]
        self.assertEqual(first["kind"], "chord")
        self.assertEqual(first["key"], "as")
        self.assertEqual(first["at_ms"], 0.0)
        self.assertEqual(second["at_ms"], 250.0)
        self.assertAlmostEqual(first["duration_ms"], 145.0, places=3)
        self.assertEqual(second["duration_ms"], 250.0)

    def test_performance_preview_removes_leading_recording_silence_like_external_player(self):
        preview = build_performance_preview(
            [{"key": "a", "at_ms": 4200, "duration_ms": 80}],
            PlaybackOptions(speed=1),
        )
        self.assertEqual(preview["events"][0]["at_ms"], 0.0)

    def test_ui_exposes_internal_play_next_to_dry_run(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        dry = html.index('id="dryRun"')
        internal = html.index('id="internalPlay"')
        self.assertGreater(internal, dry)
        self.assertLess(internal - dry, 400)
        self.assertIn("Internal play", html)

    def test_internal_preview_has_dedicated_non_outputting_api_routes(self):
        server = Path("app/server.py").read_text(encoding="utf-8")
        api = Path("web/api.js").read_text(encoding="utf-8")
        self.assertIn('path == "/api/preview"', server)
        self.assertIn('path == "/api/preview-performance"', server)
        self.assertIn('request("/api/preview"', api)
        self.assertIn('request("/api/preview-performance"', api)

    def test_browser_preview_routes_to_builtin_piano_not_keyboard_api(self):
        preview_js = Path("web/internal_preview.js").read_text(encoding="utf-8")
        app_js = Path("web/app.js").read_text(encoding="utf-8")
        self.assertIn("LocalPianoOutput", preview_js)
        self.assertIn("internalPreview.start", app_js)
        self.assertIn("internalPreview.seek", app_js)
        self.assertIn("internalPreview.togglePause", app_js)
        self.assertIn('event.key === "F7"', app_js)

    def test_touched_source_files_stay_under_450_lines(self):
        for name in [
            "web/app.js", "web/internal_preview.js", "web/piano.js", "web/ui_helpers.js",
            "app/preview_timeline.py", "app/server.py",
        ]:
            count = len(Path(name).read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(count, 450, f"{name} has {count} lines")


if __name__ == "__main__":
    unittest.main()
