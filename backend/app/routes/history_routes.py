"""/api/projects/{slug}/history/* — commits, diffs, restore."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from .. import auth, events, search, versioning
from ..util import proj_or_404

router = APIRouter(prefix="/api/projects", tags=["history"])


@router.get("/{slug}/history")
def history(slug: str, limit: int = 50) -> list[dict]:
    return versioning.history(proj_or_404(slug).vault_dir, limit=limit)


@router.get("/{slug}/history/file")
def file_history(slug: str, path: str, limit: int = 50) -> list[dict]:
    return versioning.file_history(proj_or_404(slug).vault_dir, path, limit=limit)


@router.get("/{slug}/history/show")
def history_show(slug: str, commit: str, path: str) -> PlainTextResponse:
    content = versioning.show_at(proj_or_404(slug).vault_dir, commit, path)
    if content is None:
        raise HTTPException(status_code=404, detail="not in commit")
    return PlainTextResponse(content)


@router.get("/{slug}/history/diff")
def history_diff(slug: str, commit: str, path: str | None = None) -> PlainTextResponse:
    return PlainTextResponse(versioning.diff(proj_or_404(slug).vault_dir, commit, path))


@router.post("/{slug}/history/restore", dependencies=[Depends(auth.require_project)])
def history_restore(slug: str, commit: str, path: str) -> dict:
    proj = proj_or_404(slug)
    ok = versioning.restore(proj.vault_dir, commit, path)
    if not ok:
        raise HTTPException(status_code=404, detail="not in commit")
    search.update_file(proj.vault_dir, proj.vault_dir / path)
    events.emit("fs", {"project": slug, "path": path, "op": "restored"})
    return {"ok": True}
