import tempfile
import unittest
from pathlib import Path

from app.audio_note_cleanup import basic_pitch_args, performance_from_note_events, preset_for
from app.playback import PlaybackOptions
from app.preview_timeline import build_performance_preview


class V047RhythmPreservationTests(unittest.TestCase):
    def test_rhythm_preset_keeps_fast_note_floor(self):
        preset = preset_for("rhythm")
        args = basic_pitch_args(preset)
        idx = args.index("--minimum-note-length")
        self.assertLessEqual(float(args[idx + 1]), 60.0)
        self.assertLess(preset.retrigger_window_ms, 20.0)
        self.assertLess(preset.chord_window_ms, 20.0)

    def test_rhythm_cleanup_preserves_fast_repeated_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.csv"
            path.write_text(
                "start_time_s,end_time_s,pitch_midi,velocity,pitch_bend\n"
                "0.000,0.060,60,90,\n"
                "0.070,0.130,60,88,\n"
                "0.140,0.200,62,91,\n", encoding="utf-8")
            performance, stats = performance_from_note_events(path, preset_for("rhythm"))
            self.assertEqual(len(performance), 3)
            self.assertGreaterEqual(stats["note_count"], 3)

    def test_internal_transcribed_preview_caps_hold_before_next_onset(self):
        events = [
            {"key": "a", "at_ms": 0, "duration_ms": 500, "midi_notes": [60]},
            {"key": "s", "at_ms": 80, "duration_ms": 500, "midi_notes": [62]},
        ]
        options = PlaybackOptions(
            speed=1.0, gate_percent=58, modifier_lead_ms=6, chord_spread_ms=4,
            timing_profile="youtube_basic_pitch", piano_layout="88",
        )
        preview = build_performance_preview(events, options)
        self.assertLess(preview["events"][0]["duration_ms"], 80)
        self.assertAlmostEqual(preview["events"][1]["at_ms"], 80.0, places=3)

    def test_ui_keeps_rhythm_mode_and_uses_current_default(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        js = Path("web/youtube_piano.js").read_text(encoding="utf-8")
        server = Path("app/server.py").read_text(encoding="utf-8")
        self.assertIn('value="rhythm"', html)
        self.assertIn('Rhythm preserve — maximum sensitivity', html)
        self.assertIn('value="rhythm_clean"', html)
        self.assertIn('quality?.value || "rhythm_accurate"', js)
        self.assertIn('str(payload.get("quality") or "rhythm_accurate")', server)
        self.assertRegex(html, r"Piano Auto Player v0\.\d+\.\d+")
        self.assertRegex(server, r"Piano Auto Player v0\.\d+\.\d+ running")

    def test_source_line_cap(self):
        for name in [
            "app/audio_note_cleanup.py", "app/audio_transcriber.py", "app/playback.py",
            "app/preview_timeline.py", "app/server.py", "web/youtube_piano.js", "web/app.js",
        ]:
            lines = len(Path(name).read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(lines, 450, f"{name} exceeded 450 lines ({lines})")


if __name__ == "__main__":
    unittest.main()
