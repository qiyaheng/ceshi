# Start local model server (OpenAI-compatible, port 8081)
# Usage: powershell -ExecutionPolicy Bypass -File scripts\start_local_model.ps1
param(
    [string]$ModelPath = "models\qwen3-4b-q4_k_m.gguf",
    [int]$Port = 8081,
    [int]$CtxSize = 8192
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$model = Join-Path $root $ModelPath
if (-not (Test-Path $model)) {
    Write-Error "Model file not found: $model (run scripts\download_model.ps1 first)"
    exit 1
}

Write-Host "Starting local model: $model (port $Port, ctx $CtxSize)"
# 使用 GGUF 内置 Qwen3 对话模板（生成质量正常）；<tool_call> 标签由后端自行解析
Push-Location $root
& "$root\.venv\Scripts\python.exe" -m llama_cpp.server `
    --model $ModelPath `
    --model_alias qwen3-4b `
    --host 127.0.0.1 `
    --port $Port `
    --n_ctx $CtxSize
Pop-Location
