#!/usr/bin/env bash
# Start local model server (OpenAI-compatible, port 8081)
# Usage: bash scripts/start_local_model.sh
set -e

MODEL_PATH="${1:-models/qwen3-4b-q4_k_m.gguf}"
PORT="${2:-8081}"
CTX_SIZE="${3:-8192}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL="$ROOT/$MODEL_PATH"

if [ ! -f "$MODEL" ]; then
  echo "Model file not found: $MODEL (run scripts/download_model.sh first)" >&2
  exit 1
fi

# Pick python from venv if present
PY="$ROOT/.venv/bin/python"
[ -f "$PY" ] || PY="python3"

echo "Starting local model: $MODEL (port $PORT, ctx $CTX_SIZE)"
# Use GGUF built-in Qwen3 chat template; <tool_call> tags are parsed by our backend
cd "$ROOT"
"$PY" -m llama_cpp.server \
  --model "$MODEL_PATH" \
  --model_alias qwen3-4b \
  --host 127.0.0.1 \
  --port "$PORT" \
  --n_ctx "$CTX_SIZE"
