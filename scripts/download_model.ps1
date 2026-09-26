# Download GGUF model from ModelScope into project models\ directory
# Default: Qwen3-4B Q4_K_M (~2.5GB, good function-calling ability)
param(
    [string]$ModelUrl = "https://modelscope.cn/models/Qwen/Qwen3-4B-GGUF/resolve/master/Qwen3-4B-Q4_K_M.gguf",
    [string]$OutFile = "qwen3-4b-q4_k_m.gguf"
)

$root = Split-Path -Parent $PSScriptRoot
$dir = Join-Path $root "models"
New-Item -ItemType Directory -Force $dir | Out-Null
$out = Join-Path $dir $OutFile

if (Test-Path $out) {
    Write-Host "Already exists: $out, skip download"
    exit 0
}

Write-Host "Downloading: $ModelUrl -> $out"
curl.exe -L -o $out $ModelUrl --progress-bar
Write-Host "Done: $out"
