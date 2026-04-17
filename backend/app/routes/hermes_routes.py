"""/api/hermes/* and /api/projects/{slug}/hermes/*."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .. import auth, hermes
from ..util import proj_or_404, safe_path

router = APIRouter(prefix="/api", tags=["hermes"])


@router.get("/hermes/jobs")
def hermes_jobs(limit: int = 50) -> list[dict]:
    return [j.__dict__ for j in hermes.recent_jobs(limit=limit)]


@router.post(
    "/projects/{slug}/hermes/retrigger",
    dependencies=[Depends(auth.require_project)],
)
def hermes_retrigger(slug: str, path: str) -> dict:
    proj = proj_or_404(slug)
    src = safe_path(proj, path)
    if not src.is_file():
        raise HTTPException(status_code=404, detail="not found")
    hermes.enqueue(slug, proj.vault_dir, src)
    return {"ok": True}
