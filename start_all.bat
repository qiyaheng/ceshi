﻿@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 金融研究员 Agent - 启动器

echo ============================================
echo    金融研究员 Agent - 一键启动
echo ============================================
echo.

rem ---- 第 1 步：检查运行环境是否就绪 ----
if not exist ".venv\Scripts\python.exe" (
  echo [错误] 没有找到 Python 虚拟环境 .venv
  echo        说明依赖还没安装，请先按 README「1. 安装依赖」操作。
  echo.
  pause
  exit /b 1
)

if not exist "models\qwen3-4b-q4_k_m.gguf" (
  echo [错误] 没有找到本地模型文件 models\qwen3-4b-q4_k_m.gguf
  echo        请先双击运行 download_model.bat（或按 README 第 2 步下载模型）。
  echo.
  pause
  exit /b 1
)

if not exist ".env" (
  echo [提示] 没有找到配置文件 .env，已自动从模板 .env.example 复制一份。
  copy .env.example .env >nul
)

rem ---- 第 2 步：在两个新窗口分别启动两个服务 ----
echo [1/2] 正在启动「本地模型服务」，端口 8081，首次加载约需 30~60 秒...
start "金融研究员 - 模型服务(8081)" cmd /k "cd /d %~dp0 && powershell -ExecutionPolicy Bypass -File scripts\start_local_model.ps1"

echo [2/2] 正在启动「后端 API 服务」，端口 8080...
start "金融研究员 - 后端API(8080)" cmd /k "cd /d %~dp0 && .venv\Scripts\python.exe -m uvicorn backend.main:app --port 8080"

echo.
echo ============================================
echo  启动完成！屏幕上会多出两个黑色命令行窗口：
echo    窗口1 = 模型服务  http://localhost:8081
echo    窗口2 = 后端 API  http://localhost:8080
echo.
echo  这两个窗口不能关，关了服务就停了。
echo  要停止服务：双击 stop_all.bat
echo ============================================
echo.
pause
