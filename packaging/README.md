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
