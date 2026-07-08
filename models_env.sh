#!/usr/bin/bash

export WHISPER_MODEL=~/dev/models/whisper/ggml-large-v3-turbo.bin

export LLAMA_CLI="$HOME/dev/git/llama.cpp/build/bin/llama-cli"

# Model directories
export MODELS_DIR="$HOME/dev/models"

# Whisper models
export WHISPER_MODELS_DIR="$MODELS_DIR/whisper"
export WHISPER_MODEL="$WHISPER_MODELS_DIR/ggml-large-v3-turbo.bin"

# Ollama models
export OLLAMA_MODELS="$MODELS_DIR/ollama"

# llama.cpp / GGUF models
export LLM_MODELS_DIR="$MODELS_DIR/llm"
export MOJIOKOSHI_LLM_MODEL="$LLM_MODELS_DIR/qwen-japanese-cleaner.gguf"

# llama.cpp binary, if installed from source
export LLAMA_CPP_DIR="$HOME/dev/git/llama.cpp"
export LLAMA_CLI="$LLAMA_CPP_DIR/build/bin/llama-cli"
