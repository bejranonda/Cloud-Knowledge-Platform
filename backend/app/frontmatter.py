"""Tiny YAML-ish frontmatter parser.

Handles the subset Obsidian emits: scalar key/value, lists (- item), and
comma-separated inline lists. No need to pull in PyYAML for this.
"""
from __future__ import annotations

from typing import Any

_FENCE = "---"


def split(text: str) -> tuple[dict[str, Any], str]:
    """Return (frontmatter, body). If no frontmatter, returns ({}, text)."""
    if not text.startswith(_FENCE):
        return {}, text
    lines = text.splitlines()
    if len(lines) < 2 or lines[0].strip() != _FENCE:
        return {}, text
    end = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == _FENCE:
            end = i
            break
    if end == -1:
        return {}, text
    fm = _parse("\n".join(lines[1:end]))
    body = "\n".join(lines[end + 1 :])
    return fm, body


def _parse(src: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] | None = None
    for raw in src.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith(("- ", "  - ")) and current_key is not None and current_list is not None:
            current_list.append(raw.split("-", 1)[1].strip().strip('"').strip("'"))
            out[current_key] = current_list
            continue
        if ":" not in raw:
            continue
        k, v = raw.split(":", 1)
        k = k.strip()
        v = v.strip()
        if not v:
            current_key = k
            current_list = []
            out[k] = current_list
            continue
        current_key, current_list = None, None
        if v.startswith("[") and v.endswith("]"):
            out[k] = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",") if x.strip()]
        else:
            out[k] = v.strip('"').strip("'")
    return out


def tags_from(fm: dict[str, Any]) -> list[str]:
    raw = fm.get("tags") or fm.get("tag") or []
    if isinstance(raw, str):
        return [t.strip().lstrip("#") for t in raw.split(",") if t.strip()]
    if isinstance(raw, list):
        return [str(t).strip().lstrip("#") for t in raw if str(t).strip()]
    return []
