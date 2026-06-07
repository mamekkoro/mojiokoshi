#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import torch
from pyannote.audio import Pipeline

from transcript_lib import (
    Segment,
    Subtitle,
    build_merged_lines,
    overlap,
    read_rttm,
    read_srt,
    write_rttm,
    write_srt,
)

SCRIPT_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ChunkSpec:
    index: int
    start: float
    duration: float

    @property
    def end(self) -> float:
        return self.start + self.duration


def resolve_device(name: str) -> torch.device:
    if name != "auto":
        return torch.device(name)

    if torch.cuda.is_available():
        return torch.device("cuda")

    if torch.backends.mps.is_available():
        return torch.device("mps")

    return torch.device("cpu")


def resolve_whisper_model(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.expanduser()

    env_value = os.environ.get("WHISPER_MODEL")
    if env_value:
        return Path(env_value).expanduser()

    raise SystemExit(
        "Error: Whisper model not specified.\n"
        "Set the WHISPER_MODEL environment variable to the path of a ggml model file:\n"
        "  export WHISPER_MODEL=~/models/whisper/ggml-large-v3-turbo.bin\n"
        "Or pass --whisper-model PATH directly."
    )


def get_audio_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def plan_chunks(total_duration: float, chunk_seconds: float, overlap_seconds: float) -> list[ChunkSpec]:
    if chunk_seconds <= overlap_seconds:
        raise ValueError("--chunk-minutes must produce a chunk longer than --overlap-seconds")

    step = chunk_seconds - overlap_seconds
    chunks: list[ChunkSpec] = []
    start = 0.0
    index = 0

    while start < total_duration:
        duration = min(chunk_seconds, total_duration - start)
        chunks.append(ChunkSpec(index=index, start=start, duration=duration))
        if start + duration >= total_duration:
            break
        start += step
        index += 1

    return chunks


def core_window(chunks: list[ChunkSpec], index: int) -> tuple[float, float]:
    """Return the [lower, upper) range of global time that "belongs" to chunk[index].

    Boundaries are placed at the midpoint of the overlap with neighboring chunks,
    so every instant in the recording is covered by exactly one chunk's contribution.
    """
    chunk = chunks[index]

    if index == 0:
        lower = chunk.start
    else:
        lower = (chunk.start + chunks[index - 1].end) / 2

    if index == len(chunks) - 1:
        upper = chunk.end
    else:
        upper = (chunks[index + 1].start + chunk.end) / 2

    return lower, upper


def prepare_audio(input_file: Path, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["bash", str(SCRIPT_DIR / "prepare_audio.sh"), str(input_file), str(output_file)],
        check=True,
    )


def extract_chunk(source_wav: Path, chunk_wav: Path, start: float, duration: float) -> None:
    chunk_wav.parent.mkdir(parents=True, exist_ok=True)
    # Re-encode (rather than -c copy) so the cut is sample-accurate: stream-copying a
    # PCM WAV can overshoot the requested duration by tens of milliseconds because it
    # can only cut at existing packet boundaries. Re-encoding PCM-to-PCM is effectively
    # free (no real transcoding) and lands on the exact requested start/duration, which
    # the chunk-stitching logic relies on for correct timestamp offsets.
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(source_wav),
            "-ss", f"{start:.3f}",
            "-t", f"{duration:.3f}",
            "-ac", "1",
            "-ar", "16000",
            "-c:a", "pcm_s16le",
            str(chunk_wav),
        ],
        check=True,
        capture_output=True,
    )
    print(f"Saved: {chunk_wav}")


def transcribe_chunk(chunk_wav: Path, whisper_model: Path) -> None:
    print(f"Transcribing: {chunk_wav}")
    subprocess.run(
        [
            "whisper-cli",
            "-m", str(whisper_model),
            "-f", str(chunk_wav),
            "-l", "ja",
            "-otxt", "-osrt", "-ovtt",
        ],
        check=True,
    )


def diarize_chunk(pipeline: Pipeline, chunk_wav: Path, output_rttm: Path, num_speakers: int) -> None:
    print(f"Diarizing: {chunk_wav}")
    diarization_output = pipeline(str(chunk_wav), num_speakers=num_speakers)
    annotation = diarization_output.speaker_diarization

    output_rttm.parent.mkdir(parents=True, exist_ok=True)
    with output_rttm.open("w", encoding="utf-8") as f:
        annotation.write_rttm(f)

    print(f"Saved: {output_rttm}")


def stitch_subtitles(chunks: list[ChunkSpec], chunk_srt_paths: list[Path]) -> list[Subtitle]:
    global_subs: list[Subtitle] = []

    for index, chunk in enumerate(chunks):
        lower, upper = core_window(chunks, index)

        for subtitle in read_srt(chunk_srt_paths[index]):
            shifted = Subtitle(
                start=subtitle.start + chunk.start,
                end=subtitle.end + chunk.start,
                text=subtitle.text,
            )
            midpoint = (shifted.start + shifted.end) / 2
            if lower <= midpoint < upper:
                global_subs.append(shifted)

    return global_subs


def stitch_diarization(chunks: list[ChunkSpec], chunk_rttm_paths: list[Path]) -> list[Segment]:
    """Concatenate per-chunk RTTMs into one global RTTM with consistent speaker labels.

    Local labels (SPEAKER_00, SPEAKER_01, ...) are only meaningful within a single
    chunk's pyannote run. Consecutive chunks are stitched by matching local labels to
    already-assigned global labels based on how much their segments overlap in time
    within the shared overlap window; unmatched labels become new global speakers.
    """
    global_segments: list[Segment] = []
    previous_mapped: list[Segment] = []
    next_index = 0

    def new_label() -> str:
        nonlocal next_index
        label = f"SPEAKER_{next_index:02d}"
        next_index += 1
        return label

    for index, chunk in enumerate(chunks):
        shifted = [
            Segment(start=s.start + chunk.start, end=s.end + chunk.start, speaker=s.speaker)
            for s in read_rttm(chunk_rttm_paths[index])
        ]
        local_labels = sorted({s.speaker for s in shifted})

        if index == 0:
            mapping = {label: new_label() for label in local_labels}
        else:
            prev_chunk = chunks[index - 1]
            window_start, window_end = chunk.start, prev_chunk.end

            prev_in_window = [
                s for s in previous_mapped
                if overlap(s.start, s.end, window_start, window_end) > 0
            ]
            curr_in_window = [
                s for s in shifted
                if overlap(s.start, s.end, window_start, window_end) > 0
            ]
            global_labels = sorted({s.speaker for s in prev_in_window})

            scored_pairs: list[tuple[float, str, str]] = []
            for local_label in local_labels:
                local_segs = [s for s in curr_in_window if s.speaker == local_label]
                for global_label in global_labels:
                    global_segs = [s for s in prev_in_window if s.speaker == global_label]
                    score = sum(
                        overlap(c.start, c.end, p.start, p.end)
                        for c in local_segs
                        for p in global_segs
                    )
                    if score > 0:
                        scored_pairs.append((score, local_label, global_label))

            scored_pairs.sort(key=lambda item: item[0], reverse=True)

            mapping = {}
            used_globals: set[str] = set()
            for _, local_label, global_label in scored_pairs:
                if local_label in mapping or global_label in used_globals:
                    continue
                mapping[local_label] = global_label
                used_globals.add(global_label)

            for local_label in local_labels:
                if local_label not in mapping:
                    mapping[local_label] = new_label()

        mapped = [
            Segment(start=s.start, end=s.end, speaker=mapping[s.speaker])
            for s in shifted
        ]

        lower, upper = core_window(chunks, index)
        global_segments.extend(
            s for s in mapped if lower <= (s.start + s.end) / 2 < upper
        )

        previous_mapped = mapped

    global_segments.sort(key=lambda s: s.start)
    return global_segments


def write_merged_transcript(
    srt_path: Path,
    rttm_path: Path,
    output_path: Path,
    speaker_map: dict[str, str],
) -> None:
    subtitles = read_srt(srt_path)
    segments = read_rttm(rttm_path)
    lines = build_merged_lines(subtitles, segments, speaker_map)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the full transcription + diarization pipeline "
            "(convert -> chunk -> transcribe -> diarize -> merge) in one command."
        )
    )
    parser.add_argument("audio_file", type=Path, help="Input audio file (e.g. an mp3 recording)")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for all generated files (default: <input_dir>/pipeline/<basename>)",
    )
    parser.add_argument(
        "--chunk-minutes",
        type=float,
        default=20.0,
        help="Length of each processing chunk, in minutes (default: 20)",
    )
    parser.add_argument(
        "--overlap-seconds",
        type=float,
        default=60.0,
        help="Overlap between consecutive chunks, in seconds (default: 60)",
    )
    parser.add_argument(
        "--num-speakers",
        type=int,
        default=2,
        help="Expected number of speakers (default: 2)",
    )
    parser.add_argument(
        "--whisper-model",
        type=Path,
        default=None,
        help="Path to a whisper.cpp ggml model (default: $WHISPER_MODEL; required if not set)",
    )
    parser.add_argument(
        "--diarization-model",
        default="pyannote/speaker-diarization-3.1",
        help="Hugging Face pyannote pipeline name",
    )
    parser.add_argument(
        "--device",
        choices=["auto", "cuda", "mps", "cpu"],
        default="auto",
        help="Device to run the diarization pipeline on (auto detects CUDA, then MPS, then CPU)",
    )
    args = parser.parse_args()

    audio_file = args.audio_file.expanduser()
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    basename = audio_file.stem

    output_dir = (
        args.output_dir.expanduser()
        if args.output_dir is not None
        else audio_file.parent / "pipeline" / basename
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    chunk_seconds = args.chunk_minutes * 60.0

    # Step 1: convert to 16kHz mono WAV
    prepared_wav = output_dir / f"{basename}_16k_mono.wav"
    if prepared_wav.exists():
        print(f"Skip (exists): {prepared_wav}")
    else:
        prepare_audio(audio_file, prepared_wav)

    # Step 2: plan overlapping chunks
    duration = get_audio_duration(prepared_wav)
    chunks = plan_chunks(duration, chunk_seconds, args.overlap_seconds)
    print(f"Audio duration: {duration:.1f}s -> {len(chunks)} chunk(s)")

    chunks_dir = output_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    whisper_model = resolve_whisper_model(args.whisper_model)

    pipeline = Pipeline.from_pretrained(args.diarization_model)
    device = resolve_device(args.device)
    pipeline.to(device)
    print(f"Using device for diarization: {device}")

    chunk_srt_paths: list[Path] = []
    chunk_rttm_paths: list[Path] = []

    # Step 3: transcribe + diarize each chunk (skip steps whose outputs already exist,
    # so an interrupted run can be resumed by simply re-running the same command)
    for chunk in chunks:
        chunk_wav = chunks_dir / f"chunk_{chunk.index:04d}.wav"
        chunk_srt = chunk_wav.with_suffix(chunk_wav.suffix + ".srt")
        chunk_rttm = chunk_wav.with_suffix(chunk_wav.suffix + ".rttm")

        chunk_srt_paths.append(chunk_srt)
        chunk_rttm_paths.append(chunk_rttm)

        if chunk_wav.exists():
            print(f"Skip (exists): {chunk_wav}")
        else:
            extract_chunk(prepared_wav, chunk_wav, chunk.start, chunk.duration)

        if chunk_srt.exists():
            print(f"Skip (exists): {chunk_srt}")
        else:
            transcribe_chunk(chunk_wav, whisper_model)

        if chunk_rttm.exists():
            print(f"Skip (exists): {chunk_rttm}")
        else:
            diarize_chunk(pipeline, chunk_wav, chunk_rttm, args.num_speakers)

    # Step 4: stitch chunk SRTs into one global SRT
    global_srt = output_dir / f"{basename}_full.srt"
    if global_srt.exists():
        print(f"Skip (exists): {global_srt}")
    else:
        write_srt(stitch_subtitles(chunks, chunk_srt_paths), global_srt)
        print(f"Saved: {global_srt}")

    # Step 5: stitch chunk RTTMs into one global RTTM with consistent speaker labels
    global_rttm = output_dir / f"{basename}_full.rttm"
    if global_rttm.exists():
        print(f"Skip (exists): {global_rttm}")
    else:
        write_rttm(stitch_diarization(chunks, chunk_rttm_paths), global_rttm)
        print(f"Saved: {global_rttm}")

    # Step 6: neutral merge (SPEAKER_00 / SPEAKER_01 labels, to be renamed later)
    merged_txt = output_dir / f"{basename}_merged.txt"
    if merged_txt.exists():
        print(f"Skip (exists): {merged_txt}")
    else:
        write_merged_transcript(global_srt, global_rttm, merged_txt, speaker_map={})
        print(f"Saved: {merged_txt}")

    print()
    print("Done. Review the neutral merged transcript:")
    print(f"  less {merged_txt}")
    print()
    print("Once you know which speaker is who, assign display names without rerunning the pipeline:")
    print(
        f"  python {SCRIPT_DIR / 'merge_srt_rttm.py'} \\\n"
        f"    --srt {global_srt} \\\n"
        f"    --rttm {global_rttm} \\\n"
        f"    --output {output_dir / f'{basename}_named.txt'} \\\n"
        f"    --speaker-00 <NAME> \\\n"
        f"    --speaker-01 <NAME>"
    )


if __name__ == "__main__":
    main()
