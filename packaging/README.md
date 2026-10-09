# 后端引擎打包

用 PyInstaller 把 Python 引擎打成独立目录，供 Electron 安装包随附。
**打包配方只有一份：[`writer-backend.spec`](../writer-backend.spec)。**

```powershell
.venv\Scripts\pip install pyinstaller
.venv\Scripts\pyinstaller --noconfirm --clean --distpath desktop/backend-dist writer-backend.spec
```

打包完成后，`desktop/backend-dist/writer-backend/writer-backend.exe` 即独立引擎。

不要在命令行上另写一套 `--collect-all` 参数：历史上 README 的命令与 spec 各写一份，
spec 补了依赖而命令没补（或反之）就会静默发出残包——tiktoken 插件就是这么丢的。

### 与打包相关的两处硬要求

| 依赖 | 为什么必须随包 | 校验 |
| --- | --- | --- |
| `tiktoken_ext.openai_public` | namespace 包，`pkgutil.iter_modules()` 动态发现，静态分析抓不到；漏了则 LightRAG 构造直接抛 `ValueError: Unknown encoding o200k_base` | spec 里 `collect_submodules('tiktoken_ext')` |
| `.tiktoken-cache` | 词表现下 3.6MB，实测 46s > 检索超时上限 45s；国内网络不可达 | `prepare-release.ps1` |


## 发布前校验：本地缓存

语义搜索有**两个**开箱即坏点，两个都实际踩过：

1. **fastembed 的 embedding 模型**（`BAAI/bge-small-zh-v1.5`）：首次使用从
   HuggingFace 下载，国内不可达则静默失败。安装包通过 `electron-builder.yml`
   的 `extraResources` 携带 `.fastembed-cache`（约 182MB）。
2. **tiktoken 的 BPE 词表**（`o200k_base` / `cl100k_base`）：缺失则联网现下，
   实测 46s；而检索整体超时上限 45s，首次检索必定超时降级。词表随
   `writer-backend.spec` 打进 `_internal/tiktoken-cache/`（约 5MB）。

**打安装包前必须运行校验脚本**：

```powershell
powershell -ExecutionPolicy Bypass -File packaging/prepare-release.ps1
# PASS: 发布依赖齐备，可以打安装包。
```

缓存缺失时脚本会给出下载指引。桌面端启动时也会检查 fastembed 缓存目录，
缺失会记入 `desktop.jsonl` 警告日志。

## 发布流程（完整）

```powershell
# 1. 打包 Python 后端（spec）
.venv\Scripts\pyinstaller --noconfirm --clean --distpath desktop/backend-dist writer-backend.spec
# 2. 校验本地缓存
powershell -ExecutionPolicy Bypass -File packaging/prepare-release.ps1
# 3. 打 Electron 安装包（desktop/ 下）
cd desktop
$env:GH_TOKEN = (gh auth token)
npx electron-builder --win nsis --publish always
```
