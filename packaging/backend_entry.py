"""PyInstaller entry point for the Writer Assistant backend engine."""

import logging
import os
import sys
from pathlib import Path

from tools.cli import main

_logger = logging.getLogger("writer_assistant.backend_entry")

# writer-backend.spec 用 datas += [('.tiktoken-cache', 'tiktoken-cache')] 把词表
# 缓存放进 _internal/<这个名字>；改名字必须两边同时改，否则打包版静默退回联网
# 现下。tests/test_packaging_recipe.py 会盯着这两处是否一致。
BUNDLED_TIKTOKEN_CACHE_DIR = "tiktoken-cache"


def _configure_tiktoken_cache() -> None:
    """把 tiktoken 的词表缓存指向随包携带的离线目录。

    LightRAG 构造时用 tiktoken 编码 gpt-4o-mini（o200k_base）。缓存缺失时
    tiktoken 会去 openaipublic.blob.core.windows.net 现下 3.6MB——实测 46s，
    国内网络通常不可达；而语义检索的整体超时上限是 45s
    （tools/project_search.py::_search_timeout），首次检索必定超时降级。
    指向随包目录后毫秒级完成，且完全离线。

    已存在 TIKTOKEN_CACHE_DIR 时不覆盖：空串是 tiktoken 约定俗成的
    「禁用缓存」写法，必须原样尊重。
    """
    if "TIKTOKEN_CACHE_DIR" in os.environ:
        return
    repo_root = Path(__file__).resolve().parents[1]
    # 打包态：_internal/tiktoken-cache；开发态：仓库里的 .tiktoken-cache。
    for candidate in (
        Path(getattr(sys, "_MEIPASS", repo_root)) / BUNDLED_TIKTOKEN_CACHE_DIR,
        repo_root / ".tiktoken-cache",
    ):
        if candidate.is_dir():
            os.environ["TIKTOKEN_CACHE_DIR"] = str(candidate)
            return


def _disable_pipmaster_runtime_installs() -> None:
    """冻结包里关掉 pipmaster 的运行时安装。

    lightrag/llm/openai.py 顶层写着：

        if not pm.is_installed("openai"):
            pm.install("openai")

    冻结包里没有 dist-info（PyInstaller 不打包含元数据），is_installed() 恒为
    False，于是每个后端进程的首次语义检索都会去执行

        sys.executable -m pip install --upgrade openai

    而 sys.executable 就是打包出来的 writer-backend.exe —— 后端把自己当成 pip
    又拉起一份，argparse 认不出 `pip` 直接报错退出（实测 exit 2）。白白多花几秒、
    多起一个进程，还在日志里留下两条 ERROR。产物里的依赖本来就是齐的，在打包
    目录内跑 pip 只会破坏安装，所以直接短路：调用方收到 False（即「没装成」），
    后续 import 该包时该失败就失败，不再有副作用。
    """
    if not getattr(sys, "frozen", False):
        return
    try:
        import pipmaster
    except ImportError:  # pragma: no cover - 依赖缺失时没有可禁用的安装器
        return

    def _blocked(*args: object, **kwargs: object) -> bool:
        _logger.warning(
            "冻结运行时已禁用 pipmaster 安装调用（拒绝在打包目录内执行 pip）"
        )
        return False

    for name in ("install", "install_if_missing", "install_or_update"):
        if hasattr(pipmaster, name):
            setattr(pipmaster, name, _blocked)


if __name__ == "__main__":
    # 必须在 main() 之前设置：tiktoken 的编码是首次调用 encoding_for_model()
    # 时才构造的，而 tools.cli 的导入不会提前构造（实测导入后 ENCODINGS 为空）。
    _configure_tiktoken_cache()
    _disable_pipmaster_runtime_installs()
    sys.exit(main())
