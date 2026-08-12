# 发布前校验：确认本地 embedding 模型缓存完整（语义搜索开箱即用）
#
# 用法（在仓库根目录）：
#   powershell -ExecutionPolicy Bypass -File packaging/prepare-release.ps1
#
# 校验失败时给出下载指引；通过后即可执行 electron-builder 打安装包。

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$CacheDir = Join-Path $RepoRoot ".fastembed-cache"

Write-Host "==> 校验 embedding 模型缓存: $CacheDir"

$Required = @(
    "fast-bge-small-zh-v1.5/model_optimized.onnx",
    "fast-bge-small-zh-v1.5/tokenizer.json",
    "models--Qdrant--bge-small-zh-v1.5/refs/main"
)

$Missing = @()
foreach ($rel in $Required) {
    $path = Join-Path $CacheDir ($rel -replace "/", "\")
    if (-not (Test-Path $path)) {
        $Missing += $rel
    }
}

if ($Missing.Count -gt 0) {
    Write-Host "FAIL: 模型缓存不完整，缺少:" -ForegroundColor Red
    foreach ($m in $Missing) { Write-Host "  - $m" -ForegroundColor Red }
    Write-Host ""
    Write-Host "请先下载模型（国内需走镜像）：" -ForegroundColor Yellow
    Write-Host '  $env:HF_ENDPOINT = "https://hf-mirror.com"'
    Write-Host '  python -c "from fastembed import TextEmbedding; TextEmbedding(model_name=''BAAI/bge-small-zh-v1.5'')"'
    Write-Host "下载完成后重跑本脚本。"
    exit 1
}

$SizeMB = [math]::Round(((Get-ChildItem $CacheDir -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 0)
Write-Host "PASS: 模型缓存完整（${SizeMB} MB），可以打安装包。" -ForegroundColor Green
