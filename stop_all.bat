@echo off
chcp 65001 >nul
title 金融研究员 Agent - 停止器

echo ============================================
echo    金融研究员 Agent - 一键停止
echo ============================================
echo.
echo 正在查找并结束占用 8080、8081 端口的进程...
echo.

set FOUND=0
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080 :8081" ^| findstr "LISTENING"') do (
  echo 结束进程，PID = %%a
  taskkill /PID %%a /F >nul 2>&1
  set FOUND=1
)

ping 127.0.0.1 -n 3 >nul

netstat -ano | findstr ":8080 :8081" | findstr "LISTENING" >nul
if errorlevel 1 (
  echo.
  echo [完成] 两个服务均已停止，端口 8080 / 8081 已释放。
) else (
  echo.
  echo [警告] 仍有进程占用端口，请把上方内容截图反馈。
)
echo.
pause
