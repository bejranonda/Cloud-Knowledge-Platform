"""Read-only bridge exposing Obsidian per-vault metadata (.obsidian/) to the Web-App.

The backend never writes to .obsidian/; it only reads the JSON files that the
pre-installed Obsidian desktop app maintains there.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from . import projects

_log = logging.getLogger(__name__)

# Files whose names are allowed through get_raw()
_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _obsidian_dir(slug: str) -> Path:
    """Return the .obsidian/ path for *slug*, raising KeyError when unknown."""
    proj = projects.get(slug)
    if proj is None:
        raise KeyError(slug)
    return proj.vault_dir / ".obsidian"


def _read_json(path: Path) -> dict | list | None:
    """Parse *path* as JSON; return None and log a warning on any error."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        _log.warning("obsidian_bridge: could not read %s — %s", path, exc)
        return None


def _safe_path(base: Path, name: str) -> Path | None:
    """Resolve *base / name*, returning None if the result escapes *base*."""
    resolved = (base / name).resolve()
    try:
        resolved.relative_to(base.resolve())
        return resolved
    except ValueError:
        return None


def _as_list(value: Any, *, of_type: type = str) -> list:
    """Coerce *value* to a list, filtering items to *of_type*."""
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, of_type)]


# ---------------------------------------------------------------------------
# Starred / bookmarks normalisation
# ---------------------------------------------------------------------------

def _parse_starred(data: dict | list | None) -> list[dict]:
    """Normalise starred.json (older format) into the unified item schema."""
    if not isinstance(data, dict):
        return []
    items: list[dict] = []
    for raw in _as_list(data.get("starred"), of_type=dict):
        item_type = raw.get("type", "file")
        title = raw.get("title") or raw.get("path") or ""
        path = raw.get("path") if item_type == "file" else None
        items.append({"type": item_type, "title": str(title), "path": path})
    return items


def _parse_bookmarks(data: dict | list | None) -> list[dict]:
    """Normalise bookmarks.json (newer nested format) into the unified schema."""
    if not isinstance(data, dict):
        return []

    def _walk(nodes: list) -> list[dict]:
        out: list[dict] = []
        for node in _as_list(nodes, of_type=dict):
            node_type = node.get("type", "file")
            if node_type == "group":
                out.extend(_walk(_as_list(node.get("items"), of_type=dict)))
            else:
                title = node.get("title") or node.get("path") or ""
                path = node.get("path") if node_type == "file" else None
                out.append({"type": node_type, "title": str(title), "path": path})
        return out

    return _walk(_as_list(data.get("items"), of_type=dict))


# ---------------------------------------------------------------------------
# Workspace helpers
# ---------------------------------------------------------------------------

def _extract_leaves(node: Any, out: list[str]) -> None:
    """Recursively collect 'file' leaf paths from a workspace node tree."""
    if not isinstance(node, dict):
        return
    if node.get("type") == "leaf" and node.get("state", {}).get("type") == "markdown":
        file_path = node.get("state", {}).get("state", {}).get("file")
        if isinstance(file_path, str) and file_path not in out:
            out.append(file_path)
    for child in _as_list(node.get("children"), of_type=dict):
        _extract_leaves(child, out)


def _workspace_files(ws: dict | list | None) -> tuple[str | None, list[str], list[str]]:
    """Return (active_file, open_files, recent_files) from workspace.json."""
    if not isinstance(ws, dict):
        return None, [], []

    open_files: list[str] = []
    _extract_leaves(ws.get("main"), open_files)
    _extract_leaves(ws.get("left"), open_files)
    _extract_leaves(ws.get("right"), open_files)

    # lastOpenFiles is a flat list Obsidian keeps for quick-open history
    recent_files = _as_list(ws.get("lastOpenFiles"))

    active_leaf_id: str | None = ws.get("active")
    # Obsidian stores active as a leaf id, not a path; first open file is best proxy
    active_file = open_files[0] if open_files else (recent_files[0] if recent_files else None)

    return active_file, open_files, recent_files


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_raw(slug: str, name: str) -> dict | None:
    """Return parsed JSON for <vault>/.obsidian/<name>.json, or None.

    *name* must be alphanumeric/underscore/hyphen only (no path traversal).
    Raises KeyError when *slug* is unknown.
    """
    if not _SAFE_NAME_RE.match(name):
        _log.warning("obsidian_bridge.get_raw: rejected unsafe name %r", name)
        return None

    obs_dir = _obsidian_dir(slug)
    target = _safe_path(obs_dir, f"{name}.json")
    if target is None:
        _log.warning("obsidian_bridge.get_raw: path traversal attempt for name %r", name)
        return None

    data = _read_json(target)
    return data if isinstance(data, dict) else None


def starred(slug: str) -> list[dict]:
    """Unified starred / bookmarked items across bookmarks.json and starred.json.

    Prefers bookmarks.json (newer); falls back to starred.json.
    Raises KeyError when *slug* is unknown.
    """
    obs_dir = _obsidian_dir(slug)
    if not obs_dir.exists():
        return []

    bm_data = _read_json(obs_dir / "bookmarks.json")
    if bm_data is not None:
        return _parse_bookmarks(bm_data)

    st_data = _read_json(obs_dir / "starred.json")
    return _parse_starred(st_data)


def recent_files(slug: str, limit: int = 20) -> list[str]:
    """Best-effort list of recently-open files from workspace.json.

    Raises KeyError when *slug* is unknown.
    """
    obs_dir = _obsidian_dir(slug)
    if not obs_dir.exists():
        return []

    ws = _read_json(obs_dir / "workspace.json")
    _, open_files, recents = _workspace_files(ws)

    # Merge: open leaves first, then lastOpenFiles, de-duped, capped at limit
    seen: set[str] = set()
    merged: list[str] = []
    for f in open_files + recents:
        if f not in seen:
            seen.add(f)
            merged.append(f)
        if len(merged) >= limit:
            break
    return merged


def plugins(slug: str) -> dict:
    """Return core and community plugin information.

    Community plugins are enriched with version/name from per-plugin manifests
    when available.
    Raises KeyError when *slug* is unknown.
    """
    obs_dir = _obsidian_dir(slug)
    if not obs_dir.exists():
        return {"core": [], "community": []}

    core = _as_list(_read_json(obs_dir / "core-plugins.json"))

    enabled_ids: list[str] = _as_list(_read_json(obs_dir / "community-plugins.json"))
    community: list[dict] = []
    plugins_dir = obs_dir / "plugins"

    for plugin_id in enabled_ids:
        entry: dict[str, Any] = {"id": plugin_id, "enabled": True, "version": None}
        manifest_path = _safe_path(plugins_dir / plugin_id, "manifest.json") if plugins_dir.exists() else None
        if manifest_path:
            manifest = _read_json(manifest_path)
            if isinstance(manifest, dict):
                entry["version"] = manifest.get("version")
                if "name" in manifest:
                    entry["name"] = manifest["name"]
        community.append(entry)

    return {"core": core, "community": community}


def summary(slug: str) -> dict:
    """Compact snapshot of the Obsidian vault metadata.

    Raises KeyError when *slug* is unknown.
    """
    obs_dir = _obsidian_dir(slug)
    has_obsidian = obs_dir.exists()

    if not has_obsidian:
        return {
            "has_obsidian": False,
            "theme": None,
            "core_plugins": [],
            "community_plugins": [],
            "workspace": {"active_file": None, "open_files": [], "recent_files": []},
            "starred": [],
            "graph_settings": {},
            "daily_notes": {},
            "templates": {},
            "settings": {
                "attachmentFolderPath": None,
                "newFileLocation": None,
                "defaultViewMode": None,
            },
        }

    # Appearance
    appearance = _read_json(obs_dir / "appearance.json") or {}
    theme = appearance.get("theme") if isinstance(appearance, dict) else None

    # Plugins
    core_plugins: list[str] = _as_list(_read_json(obs_dir / "core-plugins.json"))
    community_plugins: list[str] = _as_list(_read_json(obs_dir / "community-plugins.json"))

    # Workspace
    ws = _read_json(obs_dir / "workspace.json")
    active_file, open_files, recents = _workspace_files(ws)

    # Starred
    starred_items = starred(slug)

    # Pass-through blobs (raw dicts or empty fallback)
    graph_settings = _read_json(obs_dir / "graph.json")
    daily_notes = _read_json(obs_dir / "daily-notes.json")
    templates = _read_json(obs_dir / "templates.json")

    # Useful subset of app.json
    app_cfg = _read_json(obs_dir / "app.json") or {}
    settings_subset = {
        "attachmentFolderPath": app_cfg.get("attachmentFolderPath") if isinstance(app_cfg, dict) else None,
        "newFileLocation": app_cfg.get("newFileLocation") if isinstance(app_cfg, dict) else None,
        "defaultViewMode": app_cfg.get("defaultViewMode") if isinstance(app_cfg, dict) else None,
    }

    return {
        "has_obsidian": True,
        "theme": theme,
        "core_plugins": core_plugins,
        "community_plugins": community_plugins,
        "workspace": {
            "active_file": active_file,
            "open_files": open_files,
            "recent_files": recents,
        },
        "starred": starred_items,
        "graph_settings": graph_settings if isinstance(graph_settings, dict) else {},
        "daily_notes": daily_notes if isinstance(daily_notes, dict) else {},
        "templates": templates if isinstance(templates, dict) else {},
        "settings": settings_subset,
    }
