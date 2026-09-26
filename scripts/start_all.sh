#!/usr/bin/env bash
# 金融研究员 Agent 一键启动（macOS / Linux）
# 后台同时启动「本地模型服务(8081)」和「后端 API(8080)」，日志和进程号写入 logs/
set -e

# 切到项目根目录（本脚本在 scripts/ 下）
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

# ---- 第 1 步：检查运行环境 ----
if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "[错误] 没有找到 Python 虚拟环境 .venv，请先按 README「1. 安装依赖」操作。"
  exit 1
fi
if [ ! -f "$ROOT/models/qwen3-4b-q4_k_m.gguf" ]; then
  echo "[错误] 没有找到本地模型文件 models/qwen3-4b-q4_k_m.gguf，请先运行 bash scripts/download_model.sh"
  exit 1
fi
if [ ! -f "$ROOT/.env" ]; then
  echo "[提示] 没有找到 .env，已从 .env.example 复制一份。"
  cp "$ROOT/.env.example" "$ROOT/.env"
fi

mkdir -p "$ROOT/logs"

# ---- 第 2 步：后台启动两个服务 ----
echo "[1/2] 正在启动「本地模型服务」，端口 8081，首次加载约需 30~60 秒..."
nohup bash scripts/start_local_model.sh > logs/model.log 2>&1 &
echo $! > logs/model.pid

echo "[2/2] 正在启动「后端 API 服务」，端口 8080..."
nohup .venv/bin/python -m uvicorn backend.main:app --port 8080 > logs/backend.log 2>&1 &
echo $! > logs/backend.pid

echo ""
echo "============================================"
echo " 启动完成！两个服务在后台运行："
echo "   模型服务  http://localhost:8081   日志 logs/model.log"
echo "   后端 API  http://localhost:8080   日志 logs/backend.log"
echo ""
echo " 停止服务：bash scripts/stop_all.sh"
echo "============================================"
