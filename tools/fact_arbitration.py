"""写章后事实仲裁：正则交叉校验 LLM delta。

写章链路 settle 时，writer 返回的 ``state_delta`` 是 LLM 结算的权威来源；
这里用 ``extract_facts_from_chapter`` 的正则兜底从正文交叉抽取明显事实，
未被 delta 覆盖的（正文写到了、结算却没体现）生成审稿 issue
（``continuity_fact``），供 ReviewStore 合并进审稿记录。

仲裁是**增值服务**：任何异常只记 warning，绝不阻塞写作提交——
校验失败不能把已提交的章节打回。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .truth_manager import TruthFilesManager

logger = logging.getLogger(__name__)

DIMENSION = "continuity_fact"

_FACT_LABELS = {
    "new_characters": "新角色登场",
    "items_gained": "物品获得",
    "items_lost": "物品失去",
    "money_changes": "数值变动",
    "relationship_changes": "关系变化",
}


def _delta_blob(state_delta: Any, legacy_updates: dict[str, str]) -> str:
    """把 delta 与 legacy updates 序列化成可检索的文本。"""
    parts: list[str] = []
    if isinstance(state_delta, dict):
        operations = state_delta.get("operations", [])
        if isinstance(operations, list):
            for operation in operations:
                if not isinstance(operation, dict):
                    continue
                for key in ("value", "target", "collection"):
                    value = operation.get(key)
                    if isinstance(value, str) and value.strip():
                        parts.append(value)
                    elif isinstance(value, dict):
                        for inner in value.values():
                            if isinstance(inner, str):
                                parts.append(inner)
    for value in (legacy_updates or {}).values():
        if isinstance(value, str) and value.strip():
            parts.append(value)
    return "\n".join(parts)


def _fact_covered(fact_text: str, blob: str) -> bool:
    """事实关键词是否已被 delta 覆盖（子串匹配，宁可漏报不误报）。"""
    text = str(fact_text or "").strip()
    if not text:
        return True
    return text in blob


def _issue(description: str, suggestion: str, quote: str) -> dict[str, Any]:
    return {
        "severity": "warning",
        "category": DIMENSION,
        "description": description,
        "suggestion": suggestion,
        "evidence": {"quote": quote, "context_before": "", "context_after": ""},
    }


def arbitrate_facts(
    content: str,
    chapter_number: int,
    state_delta: dict[str, Any] | None = None,
    legacy_updates: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """交叉校验正文事实与结算 delta，返回未覆盖事实的审稿 issue。

    纯函数，不触碰文件系统，便于单元测试。
    """
    manager = TruthFilesManager(Path("unused"), "demo")
    facts = manager.extract_facts_from_chapter(content, chapter_number)
    if not facts:
        return []
    blob = _delta_blob(state_delta, legacy_updates or {})
    issues: list[dict[str, Any]] = []
    uncovered: list[tuple[str, str]] = []
    for fact_name, description in (
        ("new_characters", "新角色"),
        ("items_gained", "获得物品"),
        ("items_lost", "失去物品"),
        ("money_changes", "数值变化"),
        ("relationship_changes", "关系变化"),
    ):
        for value in facts.get(fact_name, []):
            text = str(value).strip()
            if text and not _fact_covered(text, blob):
                uncovered.append((fact_name, text))
    for fact_name, text in uncovered:
        issues.append(
            _issue(
                f"正文记录了「{text}」（{_FACT_LABELS[fact_name]}），但本章结算未体现",
                "在 state_delta 或 legacy updates 中补上这条事实，避免下章上下文丢失",
                text,
            )
        )
    return issues


def arbitrate_chapter(
    project_root: Path,
    novel_id: str,
    chapter_id: str,
    content: str,
    state_delta: dict[str, Any] | None = None,
    legacy_updates: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """完整仲裁：正文事实交叉校验 + 真相文件结构漂移检测。"""
    import re

    match = re.search(r"(\d+)", chapter_id)
    issues = arbitrate_facts(
        content, int(match.group(1)) if match else 1, state_delta, legacy_updates
    )
    try:
        for finding in TruthFilesManager(project_root, novel_id).validate_truth_structure():
            issues.append(
                _issue(
                    f"真相文件结构漂移：{finding['attr']} 的 {finding['field']} 期望 "
                    f"{finding['expected']!r}，实际 {finding['actual']!r}",
                    "恢复真相文件 TOML front matter（id/type 字段），或删除损坏文件让管理器重建",
                    finding["attr"],
                )
            )
    except Exception:
        logger.warning("truth structure validation failed", exc_info=True)
    return issues
