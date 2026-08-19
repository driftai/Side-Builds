from __future__ import annotations

"""Single-inference Basic Pitch decoding with conservative spectral evidence.

The neural network still runs once. We decode the same activations at several
thresholds. A low-threshold recovery pass is evidence only; it may not freely
add notes. Harmonic chroma and octave-specific CQT salience are attached to
candidates so the consensus layer can make high-precision rescue/prune choices.
"""

import argparse
import json
from pathlib import Path


def _tonal_profile(audio_path: str):
    import librosa
    import numpy as np

    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    if y.size == 0:
        return None, None, sr, 512, 0.0, []
    harmonic, percussive = librosa.effects.hpss(y, margin=1.0)
    hop = 512
    chroma = librosa.feature.chroma_stft(
        y=harmonic, sr=sr, n_fft=4096, hop_length=hop, center=True
    )
    chroma_peak = np.maximum(chroma.max(axis=0, keepdims=True), 1e-8)
    chroma = chroma / chroma_peak

    # Exact-pitch evidence. 88 bins from A0 through C8 line up with MIDI 21..108.
    cqt = np.abs(librosa.cqt(
        harmonic,
        sr=sr,
        hop_length=hop,
        fmin=27.5,
        n_bins=88,
        bins_per_octave=12,
    ))
    cqt_peak = np.maximum(cqt.max(axis=0, keepdims=True), 1e-8)
    cqt = cqt / cqt_peak

    harmonic_energy = float(np.mean(harmonic * harmonic))
    percussive_energy = float(np.mean(percussive * percussive))
    ratio = percussive_energy / max(1e-12, harmonic_energy + percussive_energy)
    acoustic_onsets = _acoustic_onset_profile(y, sr)
    return chroma, cqt, sr, hop, ratio, acoustic_onsets


def _acoustic_onset_profile(y, sr: int):
    import librosa
    import numpy as np

    hop = 256
    envelope = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop, n_fft=2048)
    if getattr(envelope, "size", 0) == 0:
        return []
    peak = float(np.max(envelope))
    if peak <= 1e-10:
        return []
    normalized = envelope / peak
    frames = librosa.onset.onset_detect(
        onset_envelope=normalized, sr=sr, hop_length=hop, backtrack=False, units="frames", normalize=False
    )
    half_hop_ms = 500.0 * hop / sr
    result = []
    for frame in frames:
        index = int(frame)
        if index < 0 or index >= normalized.shape[-1]:
            continue
        at_ms = max(0.0, 1000.0 * index * hop / sr - half_hop_ms)
        result.append([round(at_ms, 3), round(float(normalized[index]), 4)])
    return result


def _frame_window(start_ms: float, end_ms: float, sr: int, hop: int, frame_count: int) -> tuple[int, int]:
    start_frame = max(0, int(round((start_ms / 1000.0) * sr / hop)) - 1)
    end_probe_ms = min(end_ms, start_ms + 150.0)
    end_frame = min(frame_count, int(round((end_probe_ms / 1000.0) * sr / hop)) + 2)
    if end_frame <= start_frame:
        end_frame = min(frame_count, start_frame + 1)
    return start_frame, end_frame


def _tonal_score(start_ms: float, end_ms: float, pitch: int, chroma, sr: int, hop: int) -> float:
    if chroma is None or getattr(chroma, "size", 0) == 0:
        return 0.5
    start_frame, end_frame = _frame_window(start_ms, end_ms, sr, hop, chroma.shape[1])
    values = chroma[int(pitch) % 12, start_frame:end_frame]
    if values.size == 0:
        return 0.5
    return round(float(0.65 * values.max() + 0.35 * values.mean()), 4)


def _spectral_score(start_ms: float, end_ms: float, pitch: int, cqt, sr: int, hop: int) -> float:
    if cqt is None or getattr(cqt, "size", 0) == 0:
        return 0.5
    bin_index = int(pitch) - 21
    if bin_index < 0 or bin_index >= cqt.shape[0]:
        return 0.0
    start_frame, end_frame = _frame_window(start_ms, end_ms, sr, hop, cqt.shape[1])
    values = cqt[bin_index, start_frame:end_frame]
    if values.size == 0:
        return 0.5
    return round(float(0.60 * values.max() + 0.40 * values.mean()), 4)


def _decode(model_output, onset: float, frame: float, minimum_ms: float, min_freq: float, max_freq: float,
            chroma, cqt, sr: int, hop: int):
    from basic_pitch.constants import AUDIO_SAMPLE_RATE, FFT_HOP
    from basic_pitch.note_creation import model_output_to_notes

    copied = {key: value.copy() for key, value in model_output.items()}
    min_frames = int(round(minimum_ms / 1000.0 * (AUDIO_SAMPLE_RATE / FFT_HOP)))
    _midi, events = model_output_to_notes(
        copied,
        onset_thresh=onset,
        frame_thresh=frame,
        infer_onsets=True,
        min_note_len=min_frames,
        min_freq=min_freq,
        max_freq=max_freq,
        include_pitch_bends=False,
        multiple_pitch_bends=False,
        melodia_trick=False,
    )
    rows = []
    for start_s, end_s, pitch, amplitude, _bend in events:
        start_ms = round(float(start_s) * 1000.0, 3)
        end_ms = round(float(end_s) * 1000.0, 3)
        midi = int(pitch)
        rows.append([
            start_ms,
            end_ms,
            midi,
            max(0, min(127, int(round(float(amplitude) * 127.0)))),
            _tonal_score(start_ms, end_ms, midi, chroma, sr, hop),
            _spectral_score(start_ms, end_ms, midi, cqt, sr, hop),
        ])
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Single-inference Basic Pitch precision consensus decoder")
    parser.add_argument("audio")
    parser.add_argument("output_json")
    parser.add_argument("--layout", choices=("61", "88"), default="61")
    args = parser.parse_args()

    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import run_inference

    min_freq, max_freq = (65.406, 2093.005) if args.layout == "61" else (27.5, 4186.01)
    chroma, cqt, sr, hop, percussive_ratio, acoustic_onsets = _tonal_profile(args.audio)
    model_output = run_inference(args.audio, ICASSP_2022_MODEL_PATH)
    variants = [
        ("recovery", 0.405, 0.235),
        ("sensitive", 0.455, 0.270),
        ("primary", 0.500, 0.300),
        ("strict", 0.555, 0.335),
    ]
    payload = {
        "schema": 3,
        "minimum_note_length_ms": 55.0,
        "analysis": {
            "percussive_ratio": round(percussive_ratio, 4),
            "tonal_profile": "hpss_chroma+cqt",
            "acoustic_onsets": acoustic_onsets,
        },
        "passes": [
            {
                "name": name,
                "onset_threshold": onset,
                "frame_threshold": frame,
                "notes": _decode(model_output, onset, frame, 55.0, min_freq, max_freq, chroma, cqt, sr, hop),
            }
            for name, onset, frame in variants
        ],
    }
    Path(args.output_json).write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
