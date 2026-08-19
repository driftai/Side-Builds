from __future__ import annotations

import argparse
from pathlib import Path


def _load_audio(path: Path):
    import numpy as np
    from pydub import AudioSegment

    audio = AudioSegment.from_file(str(path))
    samples = np.array(audio.get_array_of_samples())
    samples = samples.reshape(-1, max(1, audio.channels))
    scale = float(1 << max(1, (8 * audio.sample_width) - 1))
    return int(audio.frame_rate), np.asarray(samples, dtype=np.float32) / scale


def _paths():
    import transkun

    package = Path(transkun.__file__).resolve().parent
    return package / "pretrained" / "2.0.pt", package / "pretrained" / "2.0.conf"


def _load_model(device: str):
    import moduleconf
    import torch

    weight, conf_path = _paths()
    manager = moduleconf.parseFromFile(str(conf_path))
    model_type = manager["Model"].module.TransKun
    conf = manager["Model"].config
    try:
        checkpoint = torch.load(str(weight), map_location=device, weights_only=False)
    except TypeError:
        checkpoint = torch.load(str(weight), map_location=device)
    model = model_type(conf=conf).to(device)
    state = checkpoint.get("best_state_dict", checkpoint.get("state_dict", {}))
    model.load_state_dict(state, strict=False)
    model.eval()
    return model


def transcribe(audio_path: Path, output_path: Path, device: str) -> None:
    import soxr
    import torch
    from transkun.Data import writeMidi

    model = _load_model(device)
    sample_rate, audio = _load_audio(audio_path)
    if sample_rate != model.fs:
        audio = soxr.resample(audio, sample_rate, model.fs)
    torch.set_grad_enabled(False)
    tensor = torch.from_numpy(audio).to(device)
    notes = model.transcribe(tensor, discardSecondHalf=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writeMidi(notes).write(str(output_path))


def main() -> None:
    parser = argparse.ArgumentParser(description="Piano Auto Player Transkun inference bridge")
    parser.add_argument("audio", nargs="?")
    parser.add_argument("output", nargs="?")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    device = str(args.device or "cpu")
    if args.probe:
        model = _load_model(device)
        print(f"Transkun model ready on {device} at {model.fs} Hz")
        return
    if not args.audio or not args.output:
        parser.error("audio and output are required unless --probe is used")
    transcribe(Path(args.audio), Path(args.output), device)


if __name__ == "__main__":
    main()
