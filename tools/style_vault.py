"""Style vault: browse reusable style profiles extracted from user texts."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def list_style_profiles(project_root: Path, novel_id: str) -> list[dict[str, Any]]:
    """Return every extracted source pack that can be selected as a writing style."""
    sources = (
        Path(project_root)
        / "data"
        / "novels"
        / novel_id
        / "data"
        / "sources"
    )
    profiles: list[dict[str, Any]] = []
    if not sources.is_dir():
        return profiles
    for source_dir in sorted(sources.iterdir()):
        if not source_dir.is_dir():
            continue
        style_dir = source_dir / "style"
        has_style = (style_dir / "summary.md").is_file()
        profiles.append(
            {
                "id": source_dir.name,
                "label": source_dir.name,
                "description": _profile_description(style_dir),
                "has_style": has_style,
                "ready": has_style,
            }
        )
    return profiles


def current_style_id(config: dict[str, Any]) -> str:
    return str(config.get("style_id") or "").strip()


def _profile_description(style_dir: Path) -> str:
    summary = style_dir / "summary.md"
    if not summary.is_file():
        return ""
    try:
        text = summary.read_text(encoding="utf-8")
    except OSError:
        return ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("description:"):
            return stripped.split(":", 1)[1].strip().strip('"')
        if stripped.startswith("#") and len(stripped) > 1:
            return stripped.lstrip("#").strip()
    return ""
