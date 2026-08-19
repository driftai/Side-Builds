from __future__ import annotations

from pathlib import Path
from typing import Callable

from .audio_consensus import load_consensus_notes
from .audio_note_cleanup import TranscriptionPreset, basic_pitch_args, performance_from_note_events, performance_from_notes, preset_for
from .hifi_piano import auto_accept_specialist, fuse_piano_models
from .hifi_range import compact_specialist_for_layout
from .midi_performance import midi_to_note_events, midi_to_performance


def transcribe_audio(
    run_checked: Callable[[list[str]], None],
    python: str,
    basic_pitch: str,
    audio_path: Path,
    temp: Path,
    preset: TranscriptionPreset,
    layout: str,
    engine: str = "basic_pitch",
    hifi_python: str = "",
    hifi_device: str = "cpu",
) -> tuple[list[dict], dict[str, object]]:
    """Run a model-routed audio-to-note strategy and return a timed performance."""
    if engine == "transkun":
        if not hifi_python:
            raise RuntimeError("Hi-Fi piano engine is not installed. Run setup-hifi-piano.bat once, then restart start.bat.")
        specialist = _transkun_notes(run_checked, hifi_python, hifi_device, audio_path, temp)
        specialist, range_stats = compact_specialist_for_layout(specialist, layout)
        stats = {"transcription_engine": "transkun", "hifi_route": "forced_specialist", "hifi_specialist_notes": len(specialist), "hifi_device": hifi_device, **range_stats}
        return performance_from_notes(specialist, preset_for("hifi_piano"), layout, stats)

    if preset.key == "rhythm_accurate":
        # Auto Hi-Fi always reasons about the recording in full 88-key source
        # space. The selected target layout is applied only after the models
        # have agreed/refined pitches, so a 61-key keyboard cannot distort the
        # transcription evidence itself.
        source_layout = "88" if engine == "auto_hifi" else layout
        basic_notes, consensus_stats = _basic_consensus(run_checked, python, audio_path, temp, source_layout)
        acoustic_onsets = consensus_stats.pop("_acoustic_onsets", [])
        if engine in {"auto_hifi", "transkun"}:
            if not hifi_python:
                if engine == "transkun":
                    raise RuntimeError("Hi-Fi piano engine is not installed. Run setup-hifi-piano.bat once, then restart start.bat.")
                basic_notes, range_stats = compact_specialist_for_layout(basic_notes, layout)
                consensus_stats.update(range_stats)
                consensus_stats.update({
                    "transcription_engine": "basic_pitch",
                    "hifi_fallback": "specialist_not_installed",
                    "hifi_source_space_layout": source_layout,
                })
            else:
                try:
                    specialist = _transkun_notes(run_checked, hifi_python, hifi_device, audio_path, temp)
                    fused, hifi_stats = fuse_piano_models(specialist, basic_notes, acoustic_onsets=acoustic_onsets)
                    hifi_stats["hifi_device"] = hifi_device
                    hifi_stats["hifi_source_space_layout"] = "88"
                    if auto_accept_specialist(hifi_stats):
                        fused, range_stats = compact_specialist_for_layout(fused, layout)
                        hifi_stats.update(range_stats)
                        hifi_stats.update({"transcription_engine": "hifi_fusion", "hifi_route": "source_space_consensus"})
                        return performance_from_notes(fused, preset_for("hifi_piano"), layout, hifi_stats)
                    consensus_stats.update(hifi_stats)
                    consensus_stats.update({"transcription_engine": "basic_pitch", "hifi_fallback": "low_model_agreement"})
                    basic_notes, range_stats = compact_specialist_for_layout(basic_notes, layout)
                    consensus_stats.update(range_stats)
                except RuntimeError as exc:
                    consensus_stats.update({"transcription_engine": "basic_pitch", "hifi_fallback": f"specialist_failed: {str(exc)[:180]}"})
                    basic_notes, range_stats = compact_specialist_for_layout(basic_notes, layout)
                    consensus_stats.update(range_stats)
        else:
            consensus_stats["transcription_engine"] = "basic_pitch"
        return performance_from_notes(basic_notes, preset, layout, consensus_stats)

    midi_dir = temp / "midi"
    midi_dir.mkdir(exist_ok=True)
    run_checked([basic_pitch, str(midi_dir), str(audio_path), *basic_pitch_args(preset, layout)])
    note_events = sorted(midi_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    midis = sorted([*midi_dir.glob("*.mid"), *midi_dir.glob("*.midi")], key=lambda p: p.stat().st_mtime, reverse=True)
    if not midis and not note_events:
        raise RuntimeError("Basic Pitch finished but produced no MIDI or note-event file.")
    if note_events:
        performance, stats = performance_from_note_events(note_events[0], preset, layout)
    else:
        performance, stats = midi_to_performance(midis[0].read_bytes())
        stats.update({"transcription_quality": preset.key, "transcription_quality_label": preset.label})
    stats["transcription_engine"] = "basic_pitch"
    return performance, stats


def _basic_consensus(run_checked, python: str, audio_path: Path, temp: Path, layout: str):
    output = temp / "basic_pitch_consensus.json"
    run_checked([python, "-m", "app.basic_pitch_consensus", str(audio_path), str(output), "--layout", layout])
    return load_consensus_notes(output)


def _transkun_notes(run_checked, python: str, device: str, audio_path: Path, temp: Path):
    output = temp / "transkun.mid"
    command = [python, "-m", "app.transkun_bridge", str(audio_path), str(output), "--device", device or "cpu"]
    run_checked(command)
    if not output.exists() or output.stat().st_size < 16:
        raise RuntimeError("Transkun finished but did not create a MIDI file.")
    return midi_to_note_events(output.read_bytes())
