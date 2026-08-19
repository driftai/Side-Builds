import unittest
from pathlib import Path

from app.hifi_range import compact_specialist_for_layout

ROOT = Path(__file__).resolve().parents[1]


class V0615TargetKeyAliasLifecycleTests(unittest.TestCase):
    def test_native_white_key_does_not_inherit_folded_octave_tail(self):
        # C7 (96) and C8 (108 -> 96) collapse onto the same white target key.
        notes = [(100.0, 260.0, 96, 72), (104.0, 620.0, 108, 88)]
        projected, stats = compact_specialist_for_layout(notes, "61")
        self.assertEqual(projected, [(100.0, 260.0, 96, 72)])
        self.assertEqual(stats["hifi_range_white_collision_merges"], 1)
        self.assertEqual(stats["hifi_range_alias_tails_ignored"], 1)

    def test_native_black_key_does_not_inherit_folded_octave_tail(self):
        # C#6 (85) and C#7 (97 -> 85) collapse onto one black target key.
        notes = [(100.0, 250.0, 85, 75), (108.0, 500.0, 97, 90)]
        projected, stats = compact_specialist_for_layout(notes, "61")
        self.assertEqual(projected, [(100.0, 250.0, 85, 75)])
        self.assertEqual(stats["hifi_range_black_collision_merges"], 1)
        self.assertEqual(stats["hifi_range_alias_tails_ignored"], 1)

    def test_folded_alias_cannot_repress_native_target_key_during_hold(self):
        notes = [(100.0, 300.0, 96, 80), (310.0, 470.0, 108, 76)]
        projected, stats = compact_specialist_for_layout(notes, "61")
        self.assertEqual(projected, [(100.0, 300.0, 96, 80)])
        self.assertEqual(stats["hifi_range_alias_retriggers_suppressed"], 1)
        self.assertEqual(stats["hifi_range_white_alias_conflicts"], 1)

    def test_native_note_takes_control_from_older_folded_alias(self):
        notes = [(100.0, 420.0, 108, 72), (300.0, 430.0, 96, 78)]
        projected, stats = compact_specialist_for_layout(notes, "61")
        self.assertEqual(len(projected), 2)
        self.assertEqual(projected[0][:3], (100.0, 297.0, 96))
        self.assertEqual(projected[1][:3], (300.0, 430.0, 96))
        self.assertEqual(stats["hifi_range_alias_holds_trimmed"], 1)

    def test_88_key_path_remains_exact(self):
        notes = [(100.0, 260.0, 96, 72), (104.0, 620.0, 108, 88)]
        projected, stats = compact_specialist_for_layout(notes, "88")
        self.assertEqual(projected, notes)
        self.assertEqual(stats["hifi_range_collision_merges"], 0)

    def test_version_ui_diagnostics_and_line_caps(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "web" / "youtube_piano.js").read_text(encoding="utf-8")
        server = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v0.6.21", html)
        self.assertIn("PianoAutoPlayer/0.6.21", server)
        self.assertIn("white-key alias collisions resolved", js)
        self.assertIn("folded alias retriggers suppressed", js)
        for path in [*Path(ROOT / "app").glob("*.py"), *Path(ROOT / "web").glob("*.js")]:
            self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 450, str(path))


if __name__ == "__main__":
    unittest.main()
