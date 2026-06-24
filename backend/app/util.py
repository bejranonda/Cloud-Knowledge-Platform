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
    """Resolve rel inside the vault; reject traversal or .git writes.

    Uses a real containment check (``is_relative_to``) rather than a string
    prefix: a prefix match treats sibling vaults that share a name prefix
    (e.g. ``proj-a`` vs ``proj-a-secret``) as "inside", letting a
    project-scoped token escape into another project via ``../``.
    """
    vault = proj.vault_dir.resolve()
    p = (vault / rel).resolve()
    if p != vault and not p.is_relative_to(vault):
        raise HTTPException(status_code=400, detail="path outside vault")
    if ".git" in p.parts:
        raise HTTPException(status_code=400, detail="path in .git")
    return p
