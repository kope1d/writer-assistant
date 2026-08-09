#!/usr/bin/env python3
"""工具函数模块"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Optional


def atomic_write_text(path: Any, content: str, *, encoding: str = "utf-8") -> Path:
    """原子写入文本文件：临时文件 + fsync + os.replace。

    覆盖式 write_text() 在进程中断/磁盘满时会把目标文件写坏；
    原子写保证目标文件要么是旧内容、要么是新内容，从不处于半写状态。
    异常时清理临时文件，不留下 .tmp 垃圾。
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            dir=str(target.parent),
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        temp_path.replace(target)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return target


def parse_chapter_id(user_input: str) -> Optional[str]:
    """解析用户输入的章节ID

    支持的格式:
    - "第一章" -> "ch_001"
    - "第1章" -> "ch_001"
    - "ch_001" -> "ch_001"
    - "1" -> "ch_001"
    - "5" -> "ch_005"

    Args:
        user_input: 用户输入的章节标识

    Returns:
        标准化的章节ID (ch_XXX格式)，解析失败返回None
    """
    import re

    user_input = user_input.strip()

    # 已经是标准格式
    if user_input.startswith("ch_"):
        return user_input

    # 纯数字
    if user_input.isdigit():
        num = int(user_input)
        return f"ch_{num:03d}"

    # 中文数字映射
    chinese_nums = {
        "零": 0,
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
        "百": 100,
        "千": 1000,
    }

    # 匹配 "第X章" 格式
    match = re.match(r"第([零一二三四五六七八九十百千万\d]+)章", user_input)
    if match:
        num_str = match.group(1)

        # 纯数字
        if num_str.isdigit():
            num = int(num_str)
            return f"ch_{num:03d}"

        # 中文数字转换
        num = 0
        temp = 0
        for char in num_str:
            if char in chinese_nums:
                val = chinese_nums[char]
                if val >= 10:
                    if temp == 0:
                        temp = 1
                    num += temp * val
                    temp = 0
                else:
                    temp = val
        num += temp

        if num > 0:
            return f"ch_{num:03d}"

    return None


def generate_id(name: str, id_type: str = "character") -> str:
    """将中文名转换为ID

    Args:
        name: 中文名称
        id_type: ID类型 (character | location | item | organization)

    Returns:
        转换后的ID (拼音格式)
    """
    try:
        from pypinyin import lazy_pinyin

        # 转换为拼音列表
        pinyin_list = lazy_pinyin(name)
        # 用下划线连接
        id_str = "_".join(pinyin_list).lower()
        # 移除特殊字符
        import re

        id_str = re.sub(r"[^a-z0-9_]", "", id_str)

        return id_str
    except ImportError:
        # 如果没有安装pypinyin，使用简单替换
        # 这只是fallback，建议安装pypinyin
        import hashlib
        import re

        # 移除空格和特殊字符
        id_str = re.sub(r"[^\u4e00-\u9fa5]", "", name)
        # 使用稳定哈希作为 fallback：内建 hash() 受 PYTHONHASHSEED
        # 影响，跨进程/重启会生成不同 ID，导致引用断裂。
        digest = hashlib.sha256(name.encode('utf-8')).hexdigest()[:6]
        return f"{id_type}_{digest}"


def validate_enum(value: str, enum_type: str) -> bool:
    """验证枚举值是否合法

    Args:
        value: 要验证的值
        enum_type: 枚举类型

    Returns:
        是否合法
    """
    enums = {
        "character_tier": ["protagonist", "antagonist", "supporting", "background"],
        "entity_type": ["location", "item", "organization", "event", "concept"],
        "status": ["active", "archived", "deceased", "destroyed", "hidden", "sealed"],
        "relation_type": [
            "friend",
            "enemy",
            "family",
            "lover",
            "master",
            "student",
            "rival",
        ],
    }

    return value in enums.get(enum_type, [])


if __name__ == "__main__":
    # 测试
    print("章节ID解析测试:")
    test_cases = ["第一章", "第1章", "ch_001", "1", "5", "第十章"]
    for case in test_cases:
        print(f"  {case} -> {parse_chapter_id(case)}")

    print("\nID生成测试:")
    names = ["张三", "林川", "天衡档案馆"]
    for name in names:
        print(f"  {name} -> {generate_id(name)}")
