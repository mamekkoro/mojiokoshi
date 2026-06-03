
#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 INPUT_AUDIO [OUTPUT_WAV]" >&2
  exit 1
fi

input_file="$1"

if [ "$#" -ge 2 ]; then
  output_file="$2"
else
  input_dir="$(dirname "$input_file")"
  input_base="$(basename "$input_file")"
  input_name="${input_base%.*}"
  output_dir="${input_dir}/wav"
  mkdir -p "$output_dir"
  output_file="${output_dir}/${input_name}_16k_mono.wav"
fi

mkdir -p "$(dirname "$output_file")"

ffmpeg -y \
  -i "$input_file" \
  -ac 1 \
  -ar 16000 \
  -c:a pcm_s16le \
  "$output_file"
echo "Saved: $output_file"

