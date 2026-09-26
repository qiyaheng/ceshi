#!/usr/bin/env bash
# Download GGUF model from ModelScope into project models/ directory
# Usage: bash scripts/download_model.sh
set -e

MODEL_URL="${1:-https://modelscope.cn/models/Qwen/Qwen3-4B-GGUF/resolve/master/Qwen3-4B-Q4_K_M.gguf}"
OUT_FILE="${2:-qwen3-4b-q4_k_m.gguf}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIR="$ROOT/models"
mkdir -p "$DIR"
OUT="$DIR/$OUT_FILE"

if [ -f "$OUT" ]; then
  echo "Already exists: $OUT, skip download"
  exit 0
fi

echo "Downloading: $MODEL_URL -> $OUT"
curl -L -o "$OUT" "$MODEL_URL" --progress-bar
echo "Done: $OUT"
