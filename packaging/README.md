# 后端引擎打包

用 PyInstaller 把 Python 引擎打成独立目录，供 Electron 安装包随附：

```powershell
.venv\Scripts\pip install pyinstaller
.venv\Scripts\pyinstaller --noconfirm --clean --onedir --name writer-backend `
  --paths . `
  --collect-all lightrag --collect-all fastembed --collect-all litellm `
  --collect-all onnxruntime `
  --add-data "tools/studio_assets;tools/studio_assets" `
  --add-data "tools/runtime_skills;tools/runtime_skills" `
  --add-data "craft;craft" `
  --add-data "skills;skills" `
  --distpath desktop/backend-dist `
  packaging/backend_entry.py
```

打包完成后，`desktop/backend-dist/writer-backend/writer-backend.exe` 即独立引擎。

## 发布前校验：embedding 模型缓存

本地语义搜索依赖 `BAAI/bge-small-zh-v1.5`（fastembed 首次使用从 HuggingFace
下载，国内网络不可达会静默失败——曾导致发布包语义搜索开箱即坏）。安装包通过
`electron-builder.yml` 的 `extraResources` 携带 `.fastembed-cache`（约 182MB），
**打安装包前必须运行校验脚本**：

```powershell
powershell -ExecutionPolicy Bypass -File packaging/prepare-release.ps1
# PASS: 模型缓存完整（182 MB），可以打安装包。
```

缓存缺失时脚本会给出下载指引（`HF_ENDPOINT=https://hf-mirror.com` 镜像下载）。
桌面端启动时也会检查缓存目录，缺失会记入 `desktop.jsonl` 警告日志。

## 发布流程（完整）

```powershell
# 1. 打包 Python 后端（上面 PyInstaller 命令）
# 2. 校验模型缓存
powershell -ExecutionPolicy Bypass -File packaging/prepare-release.ps1
# 3. 打 Electron 安装包（desktop/ 下）
cd desktop
$env:GH_TOKEN = (gh auth token)
npx electron-builder --win nsis --publish always
```
