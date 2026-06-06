from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    speaker: str


@dataclass(frozen=True)
class Subtitle:
    start: float
    end: float
    text: str


def parse_srt_time(value: str) -> float:
    # Example: 00:01:23,456
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(",")
    return (
        int(hours) * 3600
        + int(minutes) * 60
        + int(seconds)
        + int(millis) / 1000
    )


def format_time(seconds: float) -> str:
    total = int(seconds)
    millis = int(round((seconds - total) * 1000))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}.{millis:03d}"


def format_srt_time(seconds: float) -> str:
    total = int(seconds)
    millis = int(round((seconds - total) * 1000))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d},{millis:03d}"


def read_srt(path: Path) -> list[Subtitle]:
    content = path.read_text(encoding="utf-8", errors="replace")
    blocks = re.split(r"\n\s*\n", content.strip())

    subtitles: list[Subtitle] = []

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue

        time_line = lines[1]
        if " --> " not in time_line:
            continue

        start_text, end_text = time_line.split(" --> ", maxsplit=1)
        start = parse_srt_time(start_text)
        end = parse_srt_time(end_text)

        text = " ".join(lines[2:])
        subtitles.append(Subtitle(start=start, end=end, text=text))

    return subtitles


def read_rttm(path: Path) -> list[Segment]:
    segments: list[Segment] = []

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue

        fields = line.split()
        if len(fields) < 8:
            continue

        if fields[0] != "SPEAKER":
            continue

        start = float(fields[3])
        duration = float(fields[4])
        speaker = fields[7]

        segments.append(
            Segment(
                start=start,
                end=start + duration,
                speaker=speaker,
            )
        )

    return segments


def write_srt(subtitles: list[Subtitle], path: Path) -> None:
    lines: list[str] = []

    for index, subtitle in enumerate(subtitles, start=1):
        lines.append(str(index))
        lines.append(
            f"{format_srt_time(subtitle.start)} --> {format_srt_time(subtitle.end)}"
        )
        lines.append(subtitle.text)
        lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_rttm(segments: list[Segment], path: Path, *, uri: str = "<NA>") -> None:
    lines: list[str] = []

    for segment in segments:
        duration = segment.end - segment.start
        lines.append(
            f"SPEAKER {uri} 1 {segment.start:.3f} {duration:.3f} "
            f"<NA> <NA> {segment.speaker} <NA> <NA>"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def choose_speaker(subtitle: Subtitle, segments: list[Segment]) -> str:
    scores: dict[str, float] = {}

    for segment in segments:
        ov = overlap(subtitle.start, subtitle.end, segment.start, segment.end)
        if ov <= 0:
            continue
        scores[segment.speaker] = scores.get(segment.speaker, 0.0) + ov

    if not scores:
        return "UNKNOWN"

    return max(scores.items(), key=lambda item: item[1])[0]


def build_merged_lines(
    subtitles: list[Subtitle],
    segments: list[Segment],
    speaker_map: dict[str, str],
) -> list[str]:
    output_lines: list[str] = []

    previous_speaker: str | None = None
    buffer: list[str] = []
    buffer_start: float | None = None
    buffer_end: float | None = None

    def flush() -> None:
        nonlocal previous_speaker, buffer, buffer_start, buffer_end

        if previous_speaker is None or not buffer:
            return

        display = speaker_map.get(previous_speaker, previous_speaker)
        start_text = format_time(buffer_start if buffer_start is not None else 0.0)
        end_text = format_time(buffer_end if buffer_end is not None else 0.0)
        text = " ".join(buffer)

        output_lines.append(f"[{start_text} - {end_text}] {display}：{text}")

        buffer = []
        buffer_start = None
        buffer_end = None

    for subtitle in subtitles:
        speaker = choose_speaker(subtitle, segments)

        if previous_speaker is None:
            previous_speaker = speaker
            buffer_start = subtitle.start

        if speaker != previous_speaker:
            flush()
            previous_speaker = speaker
            buffer_start = subtitle.start

        buffer.append(subtitle.text)
        buffer_end = subtitle.end

    flush()

    return output_lines
