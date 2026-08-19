import unittest
from pathlib import Path


class V039PreviewPianoTests(unittest.TestCase):
    def test_ui_exposes_layout_aware_sound_choices(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        self.assertIn('id="pianoSound"', html)
        for value in ["acoustic_grand", "bright_acoustic", "electric_grand", "honky_tonk", "legacy_synth"]:
            self.assertIn(f'value="{value}"', html)
        self.assertIn('id="pianoVisualMeta"', html)
        self.assertRegex(html, r"Piano Auto Player v0\.\d+\.\d+")

    def test_practice_piano_is_generated_from_selected_midi_range(self):
        js = Path("web/piano.js").read_text(encoding="utf-8")
        self.assertIn("const FULL_MIN = 21", js)
        self.assertIn("const FULL_MAX = 108", js)
        self.assertIn('container.dataset.layout = mode', js)
        self.assertIn('button.dataset.midi = String(midi)', js)
        self.assertIn('container.classList.toggle("piano-88", mode === "88")', js)
        self.assertIn('Ctrl+${CTRL_RANGE_KEYS', js)

    def test_internal_and_manual_key_highlights_are_distinct(self):
        piano = Path("web/piano.js").read_text(encoding="utf-8")
        css = Path("web/styles.css").read_text(encoding="utf-8")
        self.assertIn('setKeyState(this.container, midi, "preview-active", true)', piano)
        self.assertIn('button.classList.add("manual-active")', piano)
        self.assertIn(".white-key.preview-active", css)
        self.assertIn(".white-key.manual-active", css)

    def test_generaluser_sampled_pianos_use_direct_web_audio_renderer(self):
        js = Path("web/piano_sound.js").read_text(encoding="utf-8")
        for filename in [
            "0000_GeneralUserGS_sf2_file.js",
            "0010_GeneralUserGS_sf2_file.js",
            "0020_GeneralUserGS_sf2_file.js",
            "0030_GeneralUserGS_sf2_file.js",
        ]:
            self.assertIn(filename, js)
        self.assertIn("ctx.decodeAudioData", js)
        self.assertIn("ctx.createBufferSource()", js)
        self.assertNotIn("WebAudioFontPlayer", js)

    def test_sample_failure_has_offline_fallback(self):
        controls = Path("web/piano_controls.js").read_text(encoding="utf-8")
        self.assertIn('soundSelect.value = "legacy_synth"', controls)
        self.assertIn('soundStatus.textContent = "offline fallback"', controls)
        self.assertIn("Promise.all([preview.prepareSound(), recorder.prepareSound()])", controls)

    def test_recorded_88_key_clicks_keep_source_midi(self):
        js = Path("web/piano.js").read_text(encoding="utf-8")
        self.assertIn("midi_notes: [note]", js)
        self.assertIn("key: fallbackTokenForMidi(note)", js)
        self.assertIn("recorder.noteDownMidi(midi)", js)

    def test_v039_source_files_stay_modular(self):
        for name in [
            "web/app.js", "web/internal_preview.js", "web/piano.js", "web/piano_sound.js",
            "web/piano_controls.js", "web/styles.css", "web/index.html",
        ]:
            count = len(Path(name).read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(count, 450, f"{name} has {count} lines")


if __name__ == "__main__":
    unittest.main()
