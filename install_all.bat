@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 金融研究员 Agent - 一键安装

echo ============================================
echo    金融研究员 Agent - 一键安装（Windows）
echo ============================================
echo.
echo 本脚本将自动完成：
echo   1. 检查 Python 环境
echo   2. 创建独立运行环境 .venv
echo   3. 安装全部依赖（约 5~10 分钟）
echo   4. 下载本地模型（约 2.5GB，约 10~30 分钟，取决于网速）
echo   5. 生成配置文件 .env
echo.
echo 中途如遇 Windows 安全提示，请选择"允许"。
echo ============================================
echo.
pause

rem ---- 第 1 步：检查 Python ----
echo.
echo [1/5] 检查 Python ...
python --version >nul 2>&1
if errorlevel 1 (
  echo [错误] 没有检测到 Python！
  echo        请先到 https://www.python.org/downloads/ 下载安装 Python 3.10 或更高版本，
  echo        安装时务必勾选 "Add Python to PATH"，装完重新双击本脚本。
  echo.
  pause
  exit /b 1
)
python --version

rem ---- 第 2 步：创建虚拟环境 ----
echo.
echo [2/5] 创建独立运行环境 .venv ...
if exist ".venv\Scripts\python.exe" (
  echo .venv 已存在，跳过创建。
) else (
  python -m venv .venv
  if errorlevel 1 (
    echo [错误] 创建虚拟环境失败，请把上方报错截图反馈。
    pause
    exit /b 1
  )
)

rem ---- 第 3 步：安装依赖 ----
echo.
echo [3/5] 安装 Python 依赖（耗时较长，请耐心等待，不要关闭窗口）...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :piperr
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :piperr
echo.
echo       安装本地推理引擎 llama-cpp-python（CPU 预编译版）...
".venv\Scripts\python.exe" -m pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
if errorlevel 1 goto :piperr
".venv\Scripts\python.exe" -m pip install "transformers<5" sse-starlette starlette-context
if errorlevel 1 goto :piperr

rem ---- 第 4 步：下载模型 ----
echo.
echo [4/5] 下载本地模型 Qwen3-4B（约 2.5GB）...
if exist "models\qwen3-4b-q4_k_m.gguf" (
  echo 模型文件已存在，跳过下载。
) else (
  powershell -ExecutionPolicy Bypass -File scripts\download_model.ps1
  if errorlevel 1 (
    echo [错误] 模型下载失败，通常是网络问题。请检查网络后重新双击本脚本（已完成的步骤会自动跳过）。
    pause
    exit /b 1
  )
)

rem ---- 第 5 步：生成配置 ----
echo.
echo [5/5] 生成配置文件 .env ...
if exist ".env" (
  echo .env 已存在，保留你的现有配置。
) else (
  copy .env.example .env >nul
  echo 已从模板生成 .env，默认免密钥、使用本地模型。
)

echo.
echo ============================================
echo  安装完成！
echo.
echo  下一步：双击 start_all.bat 启动服务
echo  停止服务：双击 stop_all.bat
echo.
echo  首次使用请看 README.md 的「快速开始」。
echo ============================================
echo.
pause
exit /b 0

:piperr
echo.
echo [错误] 依赖安装失败。常见原因：
echo   1. 网络不通 / pip 下载慢 —— 可配置国内镜像后重试，例如：
echo      .venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
echo   2. Python 版本过低（需要 3.10 或更高），可用 python --version 查看
echo.
pause
exit /b 1
