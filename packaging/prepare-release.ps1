# 发布前校验：确认本地缓存完整（语义搜索开箱即用）
#
# 校验两项，两者任一缺失都会让打包版的语义检索开箱即坏（都实际踩过）：
#   1. fastembed 的 embedding 模型（BAAI/bge-small-zh-v1.5）
#   2. tiktoken 的 BPE 词表（o200k_base / cl100k_base）
#
# 用法（在仓库根目录）：
#   powershell -ExecutionPolicy Bypass -File packaging/prepare-release.ps1
#
# 校验失败时给出下载指引；通过后即可执行 electron-builder 打安装包。

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$CacheDir = Join-Path $RepoRoot ".fastembed-cache"
$TiktokenCacheDir = Join-Path $RepoRoot ".tiktoken-cache"

$Failed = $false

# --- 1. fastembed embedding 模型 -----------------------------------------
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
    $Failed = $true
    Write-Host "FAIL: 模型缓存不完整，缺少:" -ForegroundColor Red
    foreach ($m in $Missing) { Write-Host "  - $m" -ForegroundColor Red }
    Write-Host ""
    Write-Host "请先下载模型（国内需走镜像）：" -ForegroundColor Yellow
    Write-Host '  $env:HF_ENDPOINT = "https://hf-mirror.com"'
    Write-Host '  python -c "from fastembed import TextEmbedding; TextEmbedding(model_name=''BAAI/bge-small-zh-v1.5'')"'
} else {
    $SizeMB = [math]::Round(((Get-ChildItem $CacheDir -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 0)
    Write-Host "PASS: 模型缓存完整（${SizeMB} MB）。" -ForegroundColor Green
}

# --- 2. tiktoken BPE 词表 -------------------------------------------------
Write-Host ""
Write-Host "==> 校验 tiktoken 词表缓存: $TiktokenCacheDir"

# 缓存文件名是词表 blob URL 的 sha1。LightRAG 用 gpt-4o-mini（o200k_base），
# lightrag 内部少数降级路径用 cl100k_base，两个都要在。
$TiktokenRequired = @(
    @{ Name = "fb374d419588a4632f3f557e76b4b70aebbca790"; Label = "o200k_base" },
    @{ Name = "9b5ad71b2ce5302211f9c61530b329a4922fc6a4"; Label = "cl100k_base" }
)

$TiktokenMissing = @()
foreach ($item in $TiktokenRequired) {
    if (-not (Test-Path (Join-Path $TiktokenCacheDir $item.Name))) {
        $TiktokenMissing += "$($item.Name)  ($($item.Label))"
    }
}

if ($TiktokenMissing.Count -gt 0) {
    $Failed = $true
    Write-Host "FAIL: tiktoken 词表缓存不完整，缺少:" -ForegroundColor Red
    foreach ($m in $TiktokenMissing) { Write-Host "  - $m" -ForegroundColor Red }
    Write-Host ""
    Write-Host "缺失时打包版会退化成联网现下（o200k_base 实测 46s，超过检索 45s 超时上限），" -ForegroundColor Yellow
    Write-Host "国内网络不可达则语义检索整体降级。请先拉取：" -ForegroundColor Yellow
    Write-Host "  `$env:TIKTOKEN_CACHE_DIR = `"$TiktokenCacheDir`""
    Write-Host '  python -c "import tiktoken; tiktoken.get_encoding(''o200k_base''); tiktoken.get_encoding(''cl100k_base'')"'
} else {
    $SizeMB = [math]::Round(((Get-ChildItem $TiktokenCacheDir -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 0)
    Write-Host "PASS: tiktoken 词表缓存完整（${SizeMB} MB）。" -ForegroundColor Green
}

Write-Host ""
if ($Failed) {
    Write-Host "FAIL: 发布依赖不完整，不要打安装包。" -ForegroundColor Red
    exit 1
}

Write-Host "PASS: 发布依赖齐备，可以打安装包。" -ForegroundColor Green
