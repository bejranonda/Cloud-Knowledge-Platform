"""Markdown wikilink graph extractor."""
from __future__ import annotations

import re
from pathlib import Path

_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")


def build(vault_dir: Path) -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []
    node_ids: set[str] = set()

    for md in vault_dir.rglob("*.md"):
        if any(part.startswith(".") for part in md.relative_to(vault_dir).parts):
            continue
        node_id = md.relative_to(vault_dir).with_suffix("").as_posix()
        node_ids.add(node_id)
        group = md.relative_to(vault_dir).parts[0] if md.parent != vault_dir else "root"
        nodes.append({"id": node_id, "label": md.stem, "group": group})

        try:
            text = md.read_text(errors="ignore")
        except OSError:
            continue
        for match in _WIKILINK_RE.finditer(text):
            target = match.group(1).strip()
            edges.append({"source": node_id, "target": target})

    # prune edges pointing to unknown nodes (or mark as dangling)
    resolved_edges = []
    for e in edges:
        target = e["target"]
        if target in node_ids:
            resolved_edges.append({**e, "dangling": False})
        else:
            # try suffix match (label only)
            candidates = [n for n in node_ids if n.endswith(f"/{target}") or n == target]
            if len(candidates) == 1:
                resolved_edges.append({"source": e["source"], "target": candidates[0], "dangling": False})
            else:
                resolved_edges.append({**e, "dangling": True})

    return {"nodes": nodes, "edges": resolved_edges}
