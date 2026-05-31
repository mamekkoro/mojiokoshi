#!/usr/bin/env bash
set -euo pipefail

MODEL="${WHISPER_MODEL:-$HOME/ssd/models/whisper/ggml-large-v3-turbo.bin}"

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
