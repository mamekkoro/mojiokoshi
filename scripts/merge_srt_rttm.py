#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from transcript_lib import build_merged_lines, read_rttm, read_srt


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge Whisper SRT transcript with pyannote RTTM diarization."
    )
    parser.add_argument("--srt", type=Path, required=True, help="Input Whisper SRT file")
    parser.add_argument("--rttm", type=Path, required=True, help="Input pyannote RTTM file")
    parser.add_argument("--output", type=Path, required=True, help="Output merged text file")
    parser.add_argument(
        "--speaker-00",
        default="SPEAKER_00",
        help="Display name for SPEAKER_00",
    )
    parser.add_argument(
        "--speaker-01",
        default="SPEAKER_01",
        help="Display name for SPEAKER_01",
    )
    args = parser.parse_args()

    subtitles = read_srt(args.srt.expanduser())
    segments = read_rttm(args.rttm.expanduser())

    speaker_map = {
        "SPEAKER_00": args.speaker_00,
        "SPEAKER_01": args.speaker_01,
    }

    output_lines = build_merged_lines(subtitles, segments, speaker_map)

    args.output.expanduser().write_text(
        "\n".join(output_lines) + "\n",
        encoding="utf-8",
    )

    print(f"Saved: {args.output.expanduser()}")


if __name__ == "__main__":
    main()
