#!/usr/bin/env bash
# 金融研究员 Agent 一键停止（macOS / Linux）
# 优先按 start_all.sh 记录的进程号停止，再用端口检查兜底
cd "$(dirname "$0")/.."

echo "============================================"
echo "   金融研究员 Agent - 一键停止"
echo "============================================"

# 第 1 步：按记录的进程号停止
for name in model backend; do
  PID_FILE="logs/${name}.pid"
  if [ -f "$PID_FILE" ]; then
    PID="$(cat "$PID_FILE")"
    if kill -0 "$PID" 2>/dev/null; then
      echo "结束 ${name} 服务，PID = ${PID}"
      kill "$PID" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
  fi
done

# 第 2 步：按端口兜底（防止进程号丢失）
sleep 2
for PORT in 8081 8080; do
  PIDS="$(lsof -ti :"$PORT" 2>/dev/null || true)"
  if [ -n "$PIDS" ]; then
    echo "端口 ${PORT} 仍被占用，强制结束 PID: ${PIDS}"
    echo "$PIDS" | xargs kill -9 2>/dev/null || true
  fi
done

sleep 1
REMAIN="$(lsof -ti :8080 -ti :8081 2>/dev/null || true)"
if [ -z "$REMAIN" ]; then
  echo "[完成] 两个服务均已停止，端口 8080 / 8081 已释放。"
else
  echo "[警告] 仍有进程占用端口: ${REMAIN}"
fi
