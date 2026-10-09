# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [('tools/studio_assets', 'tools/studio_assets'), ('tools/runtime_skills', 'tools/runtime_skills'), ('craft', 'craft'), ('skills', 'skills')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('lightrag')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('fastembed')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('litellm')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('onnxruntime')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# tiktoken 的编码插件住在独立顶层包 tiktoken_ext 里，且它是 PEP 420
# namespace 包（没有 __init__.py）。tiktoken/registry.py 靠
# pkgutil.iter_modules(tiktoken_ext.__path__) 在运行时动态发现插件，
# PyInstaller 的静态分析只看到 `import tiktoken_ext` 这一句，于是只收集到
# 一个空的 tiktoken_ext——tiktoken_ext.openai_public 根本没进 PYZ。
# 后果：encoding_for_model("gpt-4o-mini") 直接抛
#   ValueError: Unknown encoding o200k_base. Plugins found: []
# LightRAG 构造失败，打包版的语义检索整体降级为精确文本搜索（线上日志里
# 攒了 148 条 LightRAG project search failed）。
hiddenimports += collect_submodules('tiktoken_ext')

# tiktoken 的 BPE 词表离线缓存（o200k_base + cl100k_base，约 5MB）。
# 词表默认从 openaipublic.blob.core.windows.net 现下：o200k_base 实测 46s，
# 而语义检索整体超时上限是 45s（tools/project_search.py::_search_timeout），
# 首次检索必定超时；国内网络通常直接不可达。运行期由
# packaging/backend_entry.py 把 TIKTOKEN_CACHE_DIR 指向这里。
datas += [('.tiktoken-cache', 'tiktoken-cache')]


a = Analysis(
    ['packaging/backend_entry.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='writer-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='writer-backend',
)
