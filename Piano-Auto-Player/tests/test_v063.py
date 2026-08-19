import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.audio_engine import transcribe_audio
from app.audio_note_cleanup import preset_for
from app.hifi_piano import auto_accept_specialist, fuse_piano_models
from app.midi_performance import midi_to_note_events


def _vlq(value: int) -> bytes:
    parts = [value & 0x7F]
    value >>= 7
    while value:
        parts.append(0x80 | (value & 0x7F))
        value >>= 7
    return bytes(reversed(parts))


def _midi(track: bytes, ppqn: int = 480) -> bytes:
    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppqn)
    return header + b"MTrk" + struct.pack(">I", len(track)) + track


class V063HiFiConsensusTests(unittest.TestCase):
    def test_midi_note_events_preserve_velocity_and_pedal_extension(self):
        # C4 on at tick 0, pedal down, physical key up at tick 240, pedal up
        # at tick 480. At 120 BPM / 480 PPQN this should sustain to ~500ms.
        track = b"".join([
            _vlq(0), bytes([0x90, 60, 91]),
            _vlq(0), bytes([0xB0, 64, 127]),
            _vlq(240), bytes([0x80, 60, 0]),
            _vlq(240), bytes([0xB0, 64, 0]),
            _vlq(0), bytes([0xFF, 0x2F, 0x00]),
        ])
        notes = midi_to_note_events(_midi(track))
        self.assertEqual(len(notes), 1)
        start, end, pitch, velocity = notes[0]
        self.assertAlmostEqual(start, 0.0, delta=0.1)
        self.assertAlmostEqual(end, 500.0, delta=1.0)
        self.assertEqual(pitch, 60)
        self.assertEqual(velocity, 91)

    def test_fusion_prefers_specialist_and_blends_only_matching_pitch(self):
        specialist = [(100.0, 520.0, 60, 80), (400.0, 700.0, 64, 76)]
        basic = [(112.0, 500.0, 60, 60), (402.0, 690.0, 64, 58), (900.0, 980.0, 72, 45)]
        fused, stats = fuse_piano_models(specialist, basic)
        self.assertEqual(stats["hifi_model_agreements"], 2)
        self.assertEqual(stats["hifi_basic_rescued_notes"], 0)
        c4 = next(note for note in fused if note[2] == 60)
        self.assertGreater(c4[0], 100.0)
        self.assertLess(c4[0], 112.0)
        self.assertEqual(c4[3], 80)
        self.assertNotIn(72, [note[2] for note in fused])

    def test_basic_only_two_sided_repeat_hole_can_be_rescued(self):
        specialist = [(100.0, 260.0, 60, 70), (1200.0, 1380.0, 60, 72)]
        basic = [(104.0, 255.0, 60, 55), (650.0, 760.0, 60, 58), (1204.0, 1370.0, 60, 57)]
        fused, stats = fuse_piano_models(specialist, basic)
        self.assertEqual(stats["hifi_basic_rescued_notes"], 1)
        self.assertIn(650, [round(note[0]) for note in fused])

    def test_auto_accepts_plausible_agreement_and_rejects_wild_mismatch(self):
        good = {
            "hifi_agreement_f1": 0.55,
            "hifi_count_ratio": 0.92,
            "hifi_specialist_notes": 500,
        }
        wild = {
            "hifi_agreement_f1": 0.10,
            "hifi_count_ratio": 3.4,
            "hifi_specialist_notes": 900,
        }
        self.assertTrue(auto_accept_specialist(good))
        self.assertFalse(auto_accept_specialist(wild))

    def test_forced_transkun_does_not_run_basic_pitch(self):
        specialist = [(0.0, 300.0, 60, 80), (300.0, 600.0, 64, 75)]
        with tempfile.TemporaryDirectory() as td, patch("app.audio_engine._transkun_notes", return_value=specialist) as transkun:
            commands = []
            perf, stats = transcribe_audio(
                commands.append, "main-python", "basic-pitch", Path(td) / "audio.wav", Path(td),
                preset_for("rhythm_accurate"), "88", engine="transkun", hifi_python="hifi-python", hifi_device="cpu",
            )
        transkun.assert_called_once()
        self.assertEqual(commands, [])
        self.assertEqual(stats["transcription_engine"], "transkun")
        self.assertEqual(stats["hifi_route"], "forced_specialist")
        self.assertTrue(perf)

    def test_auto_hifi_missing_specialist_falls_back_to_basic_consensus(self):
        basic = [(0.0, 200.0, 60, 60), (300.0, 500.0, 64, 62)]
        with tempfile.TemporaryDirectory() as td, patch("app.audio_engine._basic_consensus", return_value=(basic, {"consensus_kept_notes": 2})):
            perf, stats = transcribe_audio(
                lambda _cmd: None, "main-python", "basic-pitch", Path(td) / "audio.wav", Path(td),
                preset_for("rhythm_accurate"), "88", engine="auto_hifi", hifi_python="",
            )
        self.assertTrue(perf)
        self.assertEqual(stats["transcription_engine"], "basic_pitch")
        self.assertEqual(stats["hifi_fallback"], "specialist_not_installed")

    def test_ui_setup_and_server_surface_v063(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        js = Path("web/youtube_piano.js").read_text(encoding="utf-8")
        api = Path("web/api.js").read_text(encoding="utf-8")
        server = Path("app/server.py").read_text(encoding="utf-8")
        setup = Path("setup-hifi-piano.bat").read_text(encoding="utf-8")
        self.assertIn('id="youtubeEngineMode"', html)
        self.assertIn('value="auto_hifi"', html)
        self.assertIn('value="transkun"', html)
        self.assertIn("cross-model", js)
        self.assertIn("engine", api)
        self.assertIn("PianoAutoPlayer/0.6.21", server)
        self.assertIn("transkun==2.0.1", setup)
        self.assertIn(".piano-hifi-venv", setup)

    def test_source_line_cap(self):
        for path in [*Path("app").glob("*.py"), *Path("web").glob("*.js")]:
            lines = len(path.read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(lines, 450, f"{path} exceeded 450 lines ({lines})")


if __name__ == "__main__":
    unittest.main()
