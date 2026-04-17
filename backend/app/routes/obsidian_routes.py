"""/api/projects/{slug}/obsidian/* — bridge to <vault>/.obsidian metadata."""
from __future__ import annotations

from fastapi import APIRouter

from .. import obsidian_bridge
from ..util import proj_or_404

router = APIRouter(prefix="/api/projects", tags=["obsidian"])


@router.get("/{slug}/obsidian/summary")
def summary(slug: str) -> dict:
    proj_or_404(slug)
    return obsidian_bridge.summary(slug)


@router.get("/{slug}/obsidian/starred")
def starred(slug: str) -> list[dict]:
    proj_or_404(slug)
    return obsidian_bridge.starred(slug)


@router.get("/{slug}/obsidian/plugins")
def plugins(slug: str) -> dict:
    proj_or_404(slug)
    return obsidian_bridge.plugins(slug)


@router.get("/{slug}/obsidian/recent")
def recent(slug: str, limit: int = 20) -> list[str]:
    proj_or_404(slug)
    return obsidian_bridge.recent_files(slug, limit=limit)
