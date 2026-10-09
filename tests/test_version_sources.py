"""版本号单一源守卫。

`tools/version.py` 是运行期唯一版本源，但同一个号还写进了 pyproject.toml、
desktop/package.json 和 desktop/package-lock.json（electron-builder 只认
package.json，发布包版本对不上会被自动更新判定为旧版）。历史上漂过两次：
一次 push 时丢了本地分支的版本改动，一次 pyproject 与 package.json 各写一套。

真源只有一个，其余都是从属；对不上就在测试里炸，而不是靠发版时想起来。
"""

import json
import re
from pathlib import Path

import pytest

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib

from tools.version import __version__

REPO_ROOT = Path(__file__).parents[1]


def test_version_is_pep440_release_tuple() -> None:
    parts = __version__.split(".")
    assert len(parts) == 3, f"版本号应为 x.y.z，实际 {__version__!r}"
    assert all(part.isdigit() for part in parts)


def test_pyproject_version_matches_runtime_version() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == __version__


def test_desktop_package_version_matches_runtime_version() -> None:
    package = json.loads((REPO_ROOT / "desktop" / "package.json").read_text(encoding="utf-8"))
    assert package["version"] == __version__


def test_desktop_lockfile_root_version_matches_runtime_version() -> None:
    lock = json.loads(
        (REPO_ROOT / "desktop" / "package-lock.json").read_text(encoding="utf-8")
    )
    # 顶层与 packages[""] 是同一条记录的两种写法，必须一起改
    assert lock["version"] == __version__
    assert lock["packages"][""]["version"] == __version__


def test_uv_lock_local_package_version_matches_runtime_version() -> None:
    """uv.lock 里本地包（editable 安装）的版本要与真源一致。

    历史上它落在 0.1.0 没跟上，而提交说明写着 “sync ... lockfile” 却根本没改到它。
    """
    lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
    local = [
        package
        for package in lock["package"]
        if package["name"] == "writer-assistant"
    ]

    assert local, "uv.lock 里应有 writer-assistant 本地包条目"
    assert local[0]["version"] == __version__


@pytest.mark.parametrize("readme_name", ["README.md", "README.en.md"])
def test_readme_version_badge_matches_runtime_version(readme_name: str) -> None:
    """首页徽章曾落后两个版本（写着 0.1.0）。"""
    readme = (REPO_ROOT / readme_name).read_text(encoding="utf-8")
    badge = re.search(r"badge/version-(\d+\.\d+\.\d+)-", readme)

    assert badge is not None, f"{readme_name} 应有 version 徽章"
    assert badge.group(1) == __version__
    assert f'alt="Version {__version__}"' in readme
