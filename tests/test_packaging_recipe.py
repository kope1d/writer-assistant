"""打包配方回归：防止发布包再次静默缺失运行期依赖。

0.2.2 发布包就是被这类缺失坑过：spec 里 `import tiktoken_ext` 静态可见，但
插件在 tiktoken_ext.openai_public 里，PyInstaller 只收集到空的 tiktoken_ext，
于是 encoding_for_model() 抛 `ValueError: Unknown encoding o200k_base`，
LightRAG 构造失败，语义搜索整体降级——直到翻用户日志才被发现。

这些断言盯着「配方文件」，因为它们不会被普通单元测试覆盖，但一改就可能
发出残包。改这里要连带改配方，不是把测试删掉。
"""

import importlib.util
import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[1]
SPEC_PATH = REPO_ROOT / "writer-backend.spec"
BACKEND_ENTRY_PATH = REPO_ROOT / "packaging" / "backend_entry.py"
RELEASE_CHECK_PATH = REPO_ROOT / "packaging" / "prepare-release.ps1"
PACKAGING_README_PATH = REPO_ROOT / "packaging" / "README.md"

# tiktoken 词表 blob URL 的 sha1（tiktoken 用它当缓存文件名）
O200K_BASE_CACHE_KEY = "fb374d419588a4632f3f557e76b4b70aebbca790"
CL100K_BASE_CACHE_KEY = "9b5ad71b2ce5302211f9c61530b329a4922fc6a4"


def _load_backend_entry():
    """按路径加载打包入口（packaging/ 不是包，且会与 PyPI 的 packaging 撞名）。"""
    spec = importlib.util.spec_from_file_location(
        "writer_backend_entry", BACKEND_ENTRY_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _isolate_tiktoken_env(monkeypatch: pytest.MonkeyPatch):
    """TIKTOKEN_CACHE_DIR 是进程级环境变量，测试后必须还原。"""
    monkeypatch.delenv("TIKTOKEN_CACHE_DIR", raising=False)


def test_backend_spec_collects_tiktoken_encoding_plugins() -> None:
    """spec 必须显式收集 tiktoken_ext 的子模块。"""
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "collect_submodules('tiktoken_ext')" in spec, (
        "writer-backend.spec 必须 collect_submodules('tiktoken_ext')。"
        "tiktoken_ext 是 PEP420 namespace 包，tiktoken/registry.py 靠 "
        "pkgutil.iter_modules() 在运行时发现编码插件，PyInstaller 静态分析"
        "看不到 tiktoken_ext.openai_public；漏了它打包版会抛 "
        "ValueError: Unknown encoding o200k_base。"
    )


def test_tiktoken_ext_really_needs_dynamic_discovery() -> None:
    """守住上面那条断言的理由：确认插件真的是动态发现的。

    若 tiktoken 某天改成静态 import，这条会失败，提示可以简化 spec。
    """
    import tiktoken.registry as registry_module

    source = Path(registry_module.__file__).read_text(encoding="utf-8")

    assert "pkgutil.iter_modules" in source
    assert "tiktoken_ext.openai_public" not in source


def test_backend_spec_bundles_tiktoken_cache_where_entry_point_reads_it() -> None:
    """spec 的 datas 目标名必须与入口读取的目录名一致。"""
    spec = SPEC_PATH.read_text(encoding="utf-8")

    match = re.search(r"\('\.tiktoken-cache',\s*'([^']+)'\)", spec)
    assert match is not None, (
        "writer-backend.spec 必须用 datas 打包 .tiktoken-cache；"
        "缺了它 tiktoken 会联网现下词表（实测 46s > 检索超时上限 45s）。"
    )

    entry = _load_backend_entry()
    assert match.group(1) == entry.BUNDLED_TIKTOKEN_CACHE_DIR


def test_configure_tiktoken_cache_respects_explicit_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = _load_backend_entry()

    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", r"D:\custom-cache")
    entry._configure_tiktoken_cache()
    assert os.environ["TIKTOKEN_CACHE_DIR"] == r"D:\custom-cache"

    # 空串是 tiktoken 约定的「禁用缓存」，不能被当成未设置而覆盖
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", "")
    entry._configure_tiktoken_cache()
    assert os.environ["TIKTOKEN_CACHE_DIR"] == ""


def test_configure_tiktoken_cache_prefers_bundled_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """打包态优先用 _internal 里随包携带的那份。"""
    entry = _load_backend_entry()

    bundled = tmp_path / entry.BUNDLED_TIKTOKEN_CACHE_DIR
    bundled.mkdir()
    monkeypatch.setattr(entry.sys, "_MEIPASS", str(tmp_path), raising=False)

    entry._configure_tiktoken_cache()

    assert os.environ["TIKTOKEN_CACHE_DIR"] == str(bundled)


def test_release_check_validates_both_local_caches() -> None:
    """发布校验脚本要同时盯住 fastembed 模型与 tiktoken 词表。"""
    script = RELEASE_CHECK_PATH.read_text(encoding="utf-8-sig")

    assert "model_optimized.onnx" in script
    assert O200K_BASE_CACHE_KEY in script
    assert CL100K_BASE_CACHE_KEY in script
    assert "exit 1" in script


def _fenced_code_blocks(markdown: str) -> list[str]:
    return re.findall(r"```[^\n]*\n(.*?)```", markdown, flags=re.DOTALL)


def test_packaging_readme_keeps_a_single_build_recipe() -> None:
    """README 的命令行不应再维护第二套打包配方。

    历史上 README 的 --collect-all 命令与 spec 各写一份，两边漂移导致
    tiktoken 插件在 spec 之外的地方丢失。配方只能有一份。

    只审代码块：正文里解释「不要再手写 --collect-all」是正当的。
    """
    readme = PACKAGING_README_PATH.read_text(encoding="utf-8")
    invocations = [
        block
        for block in _fenced_code_blocks(readme)
        if "pyinstaller" in block.lower()
    ]

    assert invocations, "README 至少要给出一条打包命令"
    for block in invocations:
        assert "writer-backend.spec" in block, (
            "打包命令必须走 writer-backend.spec；不要在 README 里另写一套 "
            "--collect-all 参数，两份配方一定会漂移。"
        )
        assert "--collect-all" not in block
