"""Shared helpers used by route modules."""
from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from . import projects


def proj_or_404(slug: str) -> projects.Project:
    p = projects.get(slug)
    if p is None:
        raise HTTPException(status_code=404, detail="project not found")
    return p


def safe_path(proj: projects.Project, rel: str) -> Path:
    """Resolve rel inside the vault; reject traversal or .git writes."""
    p = (proj.vault_dir / rel).resolve()
    if not str(p).startswith(str(proj.vault_dir.resolve())):
        raise HTTPException(status_code=400, detail="path outside vault")
    if ".git" in Path(rel).parts:
        raise HTTPException(status_code=400, detail="path in .git")
    return p
