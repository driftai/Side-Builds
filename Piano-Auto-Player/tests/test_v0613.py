import unittest
from pathlib import Path

from app.hifi_piano import HifiFusionConfig, _blend, _shift_note, fuse_piano_models

ROOT = Path(__file__).resolve().parents[1]


class V0613ReleaseSafeAttackTimingTests(unittest.TestCase):
    def test_later_attack_correction_keeps_absolute_release(self):
        stats = {}
        note = _shift_note((100.0, 300.0, 60, 70), 18.0, stats)
        self.assertEqual(note[:2], (118.0, 300.0))
        self.assertEqual(stats["hifi_attack_release_overhang_guarded"], 1)
        self.assertEqual(stats["hifi_attack_release_overhang_ms"], 18.0)

    def test_matched_note_delay_does_not_drag_release_later(self):
        stats = {}
        note = _blend((100.0, 300.0, 60, 72), (115.0, 520.0, 60, 68), HifiFusionConfig(), 16.0, stats)
        self.assertEqual(note[0], 116.0)
        self.assertEqual(note[1], 300.0)
        self.assertEqual(stats["hifi_release_secondary_tails_ignored"], 1)
        self.assertEqual(stats["hifi_attack_release_overhang_guarded"], 1)

    def test_secondary_pedal_tail_never_becomes_physical_key_hold(self):
        stats = {}
        note = _blend((200.0, 360.0, 64, 75), (203.0, 1200.0, 64, 70), HifiFusionConfig(), 0.0, stats)
        self.assertEqual(note[1], 360.0)
        self.assertEqual(stats["hifi_release_secondary_tails_ignored"], 1)

    def test_acoustic_delay_in_fusion_preserves_specialist_note_offs(self):
        specialist = [(100.0, 300.0, 60, 70), (103.0, 315.0, 64, 72)]
        basic = [(114.0, 520.0, 60, 68), (117.0, 540.0, 64, 70)]
        notes, stats = fuse_piano_models(specialist, basic, acoustic_onsets=[(120.0, 0.90)])
        by_pitch = {note[2]: note for note in notes}
        self.assertGreater(by_pitch[60][0], 104.0)
        self.assertEqual(by_pitch[60][1], 300.0)
        self.assertEqual(by_pitch[64][1], 315.0)
        self.assertGreaterEqual(stats["hifi_attack_release_overhang_guarded"], 2)
        self.assertGreaterEqual(stats["hifi_release_secondary_tails_ignored"], 2)

    def test_release_safe_patch_keeps_sustain_stitching_available(self):
        specialist = [(100.0, 200.0, 61, 70), (220.0, 330.0, 61, 68)]
        basic = [(101.0, 332.0, 61, 69)]
        notes, stats = fuse_piano_models(specialist, basic)
        pitch_notes = [note for note in notes if note[2] == 61]
        self.assertEqual(len(pitch_notes), 1)
        self.assertGreaterEqual(stats["hifi_sustain_stitches"], 1)

    def test_version_ui_diagnostics_and_line_caps(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "web" / "youtube_piano.js").read_text(encoding="utf-8")
        server = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn("Piano Auto Player v0.6.21", html)
        self.assertIn("PianoAutoPlayer/0.6.21", server)
        self.assertIn("release overhangs guarded", js)
        self.assertIn("secondary pedal tails ignored", js)
        for path in [*Path(ROOT / "app").glob("*.py"), *Path(ROOT / "web").glob("*.js")]:
            self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 450, str(path))


if __name__ == "__main__":
    unittest.main()
