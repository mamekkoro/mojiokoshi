#!/usr/bin/env bash
set -euo pipefail

if [ -z "${WHISPER_MODEL:-}" ]; then
  echo "Error: WHISPER_MODEL environment variable is not set." >&2
  echo "Set it to the path of a whisper.cpp ggml model file, e.g.:" >&2
  echo "  export WHISPER_MODEL=~/models/whisper/ggml-large-v3-turbo.bin" >&2
  exit 1
fi
MODEL="$WHISPER_MODEL"

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 AUDIO_FILE [AUDIO_FILE ...]" >&2
  exit 1
fi

for audio_file in "$@"; do
  echo "Transcribing: ${audio_file}"
  whisper-cli \
    -m "$MODEL" \
    -f "$audio_file" \
    -l ja \
    -otxt \
    -osrt \
    -ovtt
done
