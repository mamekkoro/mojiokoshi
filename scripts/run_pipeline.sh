#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage:
  run_pipeline.sh INPUT_AUDIO [options]

Options:
  --speaker-00 NAME       Display name for SPEAKER_00
  --speaker-01 NAME       Display name for SPEAKER_01
  --clean                 Run LLM cleanup step
  --summary               Run LLM summary step
  --llm-model MODEL.gguf  GGUF model path for llama.cpp
  --skip-whisper          Skip Whisper if SRT already exists
  --skip-diarize          Skip pyannote if RTTM already exists
  --help                  Show this help

Example:
  ./scripts/run_pipeline.sh ~/pclouddrv/hosh/houshasenka/20260529/kaiwa20260601.mp3 \
    --speaker-00 M職員 \
    --speaker-01 K職員 \
    --clean \
    --summary \
    --llm-model ~/ssd/models/llm/model.gguf
USAGE
}

if [ "$#" -lt 1 ]; then
  usage
  exit 1
fi

input_audio="$1"
shift

speaker_00="SPEAKER_00"
speaker_01="SPEAKER_01"
do_clean=0
do_summary=0
llm_model=""
skip_whisper=0
skip_diarize=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --speaker-00)
      speaker_00="$2"
      shift 2
      ;;
    --speaker-01)
      speaker_01="$2"
      shift 2
      ;;
    --clean)
      do_clean=1
      shift
      ;;
    --summary)
      do_summary=1
      shift
      ;;
    --llm-model)
      llm_model="$2"
      shift 2
      ;;
    --skip-whisper)
      skip_whisper=1
      shift
      ;;
    --skip-diarize)
      skip_diarize=1
      shift
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [ ! -f "$input_audio" ]; then
  echo "ERROR: input audio not found: $input_audio" >&2
  exit 1
fi

input_dir="$(dirname "$input_audio")"
input_base="$(basename "$input_audio")"
input_name="${input_base%.*}"

wav_dir="${input_dir}/wav"
wav_file="${wav_dir}/${input_name}_16k_mono.wav"

srt_file="${wav_file}.srt"
rttm_file="${wav_file}.rttm"

merged_file="${wav_dir}/${input_name}_merged.md"
named_file="${wav_dir}/${input_name}_named.md"
cleaned_file="${wav_dir}/${input_name}_cleaned.md"
summary_file="${wav_dir}/${input_name}_summary.md"

echo "== mojiokoshi pipeline =="
echo "Input : $input_audio"
echo "WAV   : $wav_file"
echo

echo "== Step 1: prepare audio =="
./scripts/prepare_audio.sh "$input_audio"

echo
echo "== Step 2: Whisper transcription =="
if [ "$skip_whisper" -eq 1 ] && [ -f "$srt_file" ]; then
  echo "Skip Whisper: $srt_file already exists"
else
  ./scripts/transcribe_whisper.sh "$wav_file"
fi

if [ ! -f "$srt_file" ]; then
  echo "ERROR: SRT file not found after Whisper: $srt_file" >&2
  exit 1
fi

echo
echo "== Step 3: pyannote diarization =="
if [ "$skip_diarize" -eq 1 ] && [ -f "$rttm_file" ]; then
  echo "Skip diarization: $rttm_file already exists"
else
  uv run python scripts/diarize_pyannote.py "$wav_file"
fi

if [ ! -f "$rttm_file" ]; then
  echo "ERROR: RTTM file not found after diarization: $rttm_file" >&2
  exit 1
fi

echo
echo "== Step 4: merge SRT and RTTM =="
uv run python scripts/merge_srt_rttm.py \
  --srt "$srt_file" \
  --rttm "$rttm_file" \
  --output "$merged_file"

uv run python scripts/merge_srt_rttm.py \
  --srt "$srt_file" \
  --rttm "$rttm_file" \
  --output "$named_file" \
  --speaker-00 "$speaker_00" \
  --speaker-01 "$speaker_01"

echo "Merged transcript: $named_file"

if [ "$do_clean" -eq 1 ]; then
  if [ -z "$llm_model" ]; then
    echo "ERROR: --clean requires --llm-model MODEL.gguf" >&2
    exit 1
  fi

  echo
  echo "== Step 5: LLM cleanup =="
  ./scripts/run_llm_text.sh \
    prompts/clean_transcript_ja.txt \
    "$named_file" \
    "$cleaned_file" \
    "$llm_model"

  echo "Cleaned transcript: $cleaned_file"
fi

if [ "$do_summary" -eq 1 ]; then
  if [ -z "$llm_model" ]; then
    echo "ERROR: --summary requires --llm-model MODEL.gguf" >&2
    exit 1
  fi

  echo
  echo "== Step 6: LLM summary =="

  summary_input="$named_file"
  if [ "$do_clean" -eq 1 ]; then
    summary_input="$cleaned_file"
  fi

  ./scripts/run_llm_text.sh \
    prompts/summarize_transcript_ja.txt \
    "$summary_input" \
    "$summary_file" \
    "$llm_model"

  echo "Summary: $summary_file"
fi

echo
echo "== Done =="
echo "Named transcript : $named_file"
[ "$do_clean" -eq 1 ] && echo "Cleaned transcript: $cleaned_file"
[ "$do_summary" -eq 1 ] && echo "Summary           : $summary_file"
