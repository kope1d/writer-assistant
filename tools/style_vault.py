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


def set_current_style_id(project_root: Path, novel_id: str, style_id: str) -> str:
    """Persist the selected style profile as the project's writing default."""
    import yaml

    style_id = style_id.strip()
    profiles = list_style_profiles(project_root, novel_id)
    if style_id and style_id not in {profile["id"] for profile in profiles}:
        raise ValueError(f"文风档案不存在: {style_id}")
    config_path = Path(project_root) / "novel_config.yaml"
    config: dict[str, Any] = {}
    if config_path.is_file():
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config = loaded if isinstance(loaded, dict) else {}
    config["style_id"] = style_id
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return style_id


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
