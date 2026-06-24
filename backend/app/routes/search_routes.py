"""/api/projects/{slug}/{search,tags,graph,backlinks}."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from .. import graph, search, tags
from ..util import proj_or_404

router = APIRouter(prefix="/api/projects", tags=["search"])


@router.get("/{slug}/search")
def project_search(slug: str, q: str, limit: int = 20) -> list[dict[str, Any]]:
    proj = proj_or_404(slug)
    hits = search.query(proj.vault_dir, q, limit=limit)
    return [{**h, "snippet": search.snippet(proj.vault_dir, h["path"], q)} for h in hits]


@router.get("/{slug}/tags")
def project_tags(slug: str) -> dict[str, Any]:
    return tags.build_index(proj_or_404(slug).vault_dir)


@router.get("/{slug}/graph")
def project_graph(slug: str) -> dict[str, Any]:
    return graph.build(proj_or_404(slug).vault_dir)


@router.get("/{slug}/backlinks")
def backlinks(slug: str, path: str) -> list[dict[str, Any]]:
    return graph.backlinks(proj_or_404(slug).vault_dir, path)
