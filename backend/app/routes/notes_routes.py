"""/api/projects/{slug}/{tree,note,note/move} — file CRUD."""
from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from .. import auth, events, search, versioning
from ..util import proj_or_404, safe_path

router = APIRouter(prefix="/api/projects", tags=["notes"])


class NoteWrite(BaseModel):
    path: str
    content: str


class NoteMove(BaseModel):
    from_: str = Field(alias="from")
    to: str

    class Config:
        populate_by_name = True


@router.get("/{slug}/tree")
def tree(slug: str) -> list[dict]:
    proj = proj_or_404(slug)
    out = []
    for p in sorted(proj.vault_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(proj.vault_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue
        st = p.stat()
        out.append({
            "path": rel.as_posix(),
            "size": st.st_size,
            "mtime": int(st.st_mtime),
            "kind": "md" if p.suffix == ".md" else "file",
        })
    return out


@router.get("/{slug}/note")
def read_note(slug: str, path: str) -> PlainTextResponse:
    proj = proj_or_404(slug)
    p = safe_path(proj, path)
    if not p.is_file():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="not found")
    return PlainTextResponse(p.read_text())


@router.put("/{slug}/note", dependencies=[Depends(auth.require_project)])
def write_note(slug: str, body: NoteWrite) -> dict:
    proj = proj_or_404(slug)
    p = safe_path(proj, body.path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body.content)
    search.update_file(proj.vault_dir, p)
    versioning.schedule_commit(proj.vault_dir, reason=f"manual: {body.path} via web-app")
    events.emit("fs", {"project": slug, "path": body.path, "op": "modified"})
    return {"ok": True, "path": body.path}


@router.delete("/{slug}/note", dependencies=[Depends(auth.require_project)])
def delete_note(slug: str, path: str) -> dict:
    from fastapi import HTTPException
    proj = proj_or_404(slug)
    p = safe_path(proj, path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="not found")
    if p.is_file():
        p.unlink()
    else:
        shutil.rmtree(p)
    search.update_file(proj.vault_dir, p)
    versioning.schedule_commit(proj.vault_dir, reason=f"manual: delete {path} via web-app")
    events.emit("fs", {"project": slug, "path": path, "op": "deleted"})
    return {"ok": True}


@router.post("/{slug}/note/move", dependencies=[Depends(auth.require_project)])
def move_note(slug: str, body: NoteMove) -> dict:
    from fastapi import HTTPException
    proj = proj_or_404(slug)
    src = safe_path(proj, body.from_)
    dst = safe_path(proj, body.to)
    if not src.exists():
        raise HTTPException(status_code=404, detail="source not found")
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    search.update_file(proj.vault_dir, src)
    search.update_file(proj.vault_dir, dst)
    versioning.schedule_commit(proj.vault_dir, reason=f"manual: move {body.from_} -> {body.to}")
    events.emit("fs", {"project": slug, "path": body.to, "op": "moved"})
    return {"ok": True}
