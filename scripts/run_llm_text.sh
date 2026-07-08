#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 4 ]; then
  echo "Usage: $0 PROMPT_FILE INPUT_TEXT OUTPUT_TEXT MODEL_FILE" >&2
  echo "Example: $0 prompts/clean_transcript_ja.txt input.md output.md ~/ssd/models/llm/model.gguf" >&2
  exit 1
fi

prompt_file="$1"
input_file="$2"
output_file="$3"
model_file="$4"

LLAMA_CLI="${LLAMA_CLI:-llama-cli}"

if ! command -v "$LLAMA_CLI" >/dev/null 2>&1; then
  echo "ERROR: llama-cli not found. Set LLAMA_CLI=/path/to/llama-cli or install llama.cpp." >&2
  exit 1
fi

if [ ! -f "$prompt_file" ]; then
  echo "ERROR: prompt file not found: $prompt_file" >&2
  exit 1
fi

if [ ! -f "$input_file" ]; then
  echo "ERROR: input file not found: $input_file" >&2
  exit 1
fi

if [ ! -f "$model_file" ]; then
  echo "ERROR: model file not found: $model_file" >&2
  exit 1
fi

tmp_prompt="$(mktemp)"
trap 'rm -f "$tmp_prompt"' EXIT

{
  cat "$prompt_file"
  echo
  echo "----- 入力 -----"
  cat "$input_file"
  echo
  echo "----- 出力 -----"
} > "$tmp_prompt"

"$LLAMA_CLI" \
  -m "$model_file" \
  -f "$tmp_prompt" \
  -n 4096 \
  --temp 0.2 \
  > "$output_file"

echo "Saved: $output_file"
