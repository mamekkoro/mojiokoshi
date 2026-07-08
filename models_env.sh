# Shared model directory for mojiokoshi
export MOJIOKOSHI_MODELS_DIR="$HOME/dev/models"

# Whisper
export WHISPER_MODELS_DIR="$MOJIOKOSHI_MODELS_DIR/whisper"
export WHISPER_MODEL="$WHISPER_MODELS_DIR/ggml-large-v3-turbo.bin"

# Ollama
export OLLAMA_MODELS="$MOJIOKOSHI_MODELS_DIR/ollama"
export MOJIOKOSHI_OLLAMA_MODEL="qwen2.5:7b-instruct"
