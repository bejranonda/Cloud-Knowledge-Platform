"""/api/projects/{slug}/dikw — DIKW-T stage breakdown.

Returns per-stage counts (Data / Information / Knowledge / Wisdom) plus
Git time-series metadata. See docs/dikw-t.md for the conceptual model.
"""
from __future__ import annotations

from fastapi import APIRouter

from .. import dikw
from ..util import proj_or_404

router = APIRouter(prefix="/api/projects", tags=["dikw"])


@router.get("/{slug}/dikw")
def dikw_summary(slug: str) -> dict:
    proj = proj_or_404(slug)
    data = dikw.summarise(proj.vault_dir)
    return {"project": proj.slug, **data}
