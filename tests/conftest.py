"""Shared test isolation fixtures."""

from __future__ import annotations

import os

import pytest


# StudioApplication 构造时 restore_environment() 会把机器真实 LLM 配置
# （含明文 API Key）从持久化 store 注入 os.environ 供子进程继承。
# 若允许这些键残留，同进程测试（或测试内部后续调用）的
# ProjectSearchIndex / LightRAG 会读到真实云凭据并走真实 embedding API，
# 表现为随机挂起或长时间等待。测试开始时即清除这些键，测试后恢复快照。
LEAKY_ENV_PREFIXES = ("LLM_", "OPENWRITE_LIGHTRAG_EMBEDDING_")


@pytest.fixture(autouse=True)
def _isolated_studio_configuration(tmp_path: Path, monkeypatch):
    """每个测试隔离 Studio 机器配置：把默认配置目录指到空目录。

    StudioApplication 构造时会从默认配置目录（default_studio_preferences_dir，
    即 ~/.config/writer-assistant/...）restore_environment() 注入机器真实的
    LLM_* 配置与明文 API Key 到进程环境；LightRAG/ProjectSearchIndex 读到后
    会走真实云 embedding，表现为随机挂起或 20s+ 超时等待。
    指向空目录后，默认 store 读不到任何配置，不注入、不走云。
    显式传入 model_settings_store 的测试不受影响（显式目录优先）。
    """
    empty_prefs = tmp_path / "empty-studio-preferences"
    empty_prefs.mkdir()
    monkeypatch.setenv("OPENWRITE_STUDIO_CONFIG_DIR", str(empty_prefs))
    snapshot = dict(os.environ)
    for key in [
        key for key in os.environ if key.startswith(LEAKY_ENV_PREFIXES)
    ]:
        os.environ.pop(key, None)
    yield
    removed = [key for key in os.environ if key not in snapshot]
    for key in removed:
        os.environ.pop(key, None)
    for key, value in snapshot.items():
        if os.environ.get(key) != value:
            os.environ[key] = value
