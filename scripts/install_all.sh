#!/usr/bin/env bash
# 金融研究员 Agent 一键安装（macOS / Linux）
# 自动完成：检查 Python → 创建 .venv → 安装依赖 → 下载模型 → 生成 .env
set -u

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PYBIN=""

echo "============================================"
echo "   金融研究员 Agent - 一键安装（macOS/Linux）"
echo "============================================"

# ---- 第 1 步：检查 Python 3.10+ ----
echo ""
echo "[1/5] 检查 Python ..."
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1; then
    ver="$("$cand" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)"
    major="${ver%%.*}"; minor="${ver##*.}"
    if [ "${major:-0}" -ge 3 ] && [ "${minor:-0}" -ge 10 ]; then
      PYBIN="$cand"
      break
    fi
  fi
done

if [ -z "$PYBIN" ]; then
  echo "[错误] 没有找到 Python 3.10 或更高版本。"
  echo "       macOS 可执行: brew install python@3.12"
  echo "       Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
  exit 1
fi
echo "使用 $($PYBIN --version 2>&1)"

# ---- 第 2 步：创建虚拟环境 ----
echo ""
echo "[2/5] 创建独立运行环境 .venv ..."
if [ -x "$ROOT/.venv/bin/python" ]; then
  echo ".venv 已存在，跳过创建。"
else
  "$PYBIN" -m venv .venv || {
    echo "[错误] 创建虚拟环境失败。Ubuntu 用户请先执行: sudo apt install python3-venv"
    exit 1
  }
fi

# ---- 第 3 步：安装依赖 ----
echo ""
echo "[3/5] 安装 Python 依赖（耗时较长，约 5~10 分钟）..."
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt || {
  echo "[错误] 依赖安装失败。如因网络慢，可加清华镜像重试："
  echo "  .venv/bin/python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple"
  exit 1
}

# macOS 编译 llama-cpp-python 需要 Xcode Command Line Tools；Linux 需要 cmake 和 gcc
if [ "$(uname -s)" = "Darwin" ]; then
  if ! xcode-select -p >/dev/null 2>&1; then
    echo ""
    echo "[提示] 首次编译需要 Xcode 命令行工具，即将弹出安装提示，请按指引完成后重跑本脚本。"
    xcode-select --install || true
    exit 1
  fi
fi
echo "      安装本地推理引擎 llama-cpp-python（从源码编译，约 3~10 分钟）..."
.venv/bin/python -m pip install llama-cpp-python || {
  echo "[错误] llama-cpp-python 编译失败。"
  echo "       Linux 请先安装编译工具: sudo apt install build-essential cmake"
  exit 1
}
.venv/bin/python -m pip install "transformers<5" sse-starlette starlette-context

# ---- 第 4 步：下载模型 ----
echo ""
echo "[4/5] 下载本地模型 Qwen3-4B（约 2.5GB）..."
if [ -f "$ROOT/models/qwen3-4b-q4_k_m.gguf" ]; then
  echo "模型文件已存在，跳过下载。"
else
  bash scripts/download_model.sh || {
    echo "[错误] 模型下载失败，通常是网络问题。检查网络后重新运行本脚本（已完成步骤会跳过）。"
    exit 1
  }
fi

# ---- 第 5 步：生成配置 ----
echo ""
echo "[5/5] 生成配置文件 .env ..."
if [ -f "$ROOT/.env" ]; then
  echo ".env 已存在，保留现有配置。"
else
  cp .env.example .env
  echo "已从模板生成 .env，默认免密钥、使用本地模型。"
fi

echo ""
echo "============================================"
echo " 安装完成！"
echo ""
echo " 启动服务: bash scripts/start_all.sh"
echo " 停止服务: bash scripts/stop_all.sh"
echo "============================================"
