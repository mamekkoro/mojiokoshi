#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import torch
from pyannote.audio import Pipeline


def resolve_device(name: str) -> torch.device:
    if name != "auto":
        return torch.device(name)

    if torch.cuda.is_available():
        return torch.device("cuda")

    if torch.backends.mps.is_available():
        return torch.device("mps")

    return torch.device("cpu")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run speaker diarization with pyannote.audio."
    )
    parser.add_argument("audio_file", type=Path, help="Input audio file")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output RTTM file",
    )
    parser.add_argument(
        "--model",
        default="pyannote/speaker-diarization-3.1",
        help="Hugging Face pyannote pipeline name",
    )
    parser.add_argument(
        "--num-speakers",
        type=int,
        default=2,
        help="Expected number of speakers",
    )
    parser.add_argument(
        "--device",
        choices=["auto", "cuda", "mps", "cpu"],
        default="auto",
        help="Device to run the pipeline on (auto detects CUDA, then MPS, then CPU)",
    )
    args = parser.parse_args()

    audio_file = args.audio_file.expanduser()
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    if args.output is None:
        output_file = audio_file.with_suffix(audio_file.suffix + ".rttm")
    else:
        output_file = args.output.expanduser()

    pipeline = Pipeline.from_pretrained(args.model)

    device = resolve_device(args.device)
    pipeline.to(device)
    print(f"Using device: {device}")

    diarization_output = pipeline(
        str(audio_file),
        num_speakers=args.num_speakers,
    )

    # pyannote.audio 4.x returns DiarizeOutput.
    # The actual Annotation object is stored in .speaker_diarization.
    annotation = diarization_output.speaker_diarization

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8") as f:
        annotation.write_rttm(f)

    print(f"Saved: {output_file}")


if __name__ == "__main__":
    main()
