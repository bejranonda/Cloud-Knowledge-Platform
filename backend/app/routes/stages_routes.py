"""DIKW-T stage actions: promote a file up the pyramid, or synthesise wisdom.

- `POST /api/projects/{slug}/promote` — move a Data file (`inbox/…`) into
  `notes/` with minimal frontmatter, upgrading it to Information. Scoped
  to that single transition; Knowledge is Hermes's job.
- `POST /api/projects/{slug}/wisdom/synthesise` — run the Wisdom stub over
  the project's `knowledge/` folder, producing `wisdom/*.md` from Git
  history. Idempotent; safe to re-run.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import auth, events, search, versioning, wisdom
from ..util import proj_or_404, safe_path

router = APIRouter(prefix="/api/projects", tags=["stages"])


class PromoteBody(BaseModel):
    path: str = Field(..., description="Relative inbox path, e.g. 'inbox/note.md'")
    title: str | None = None
    tags: list[str] | None = None


@router.post("/{slug}/promote", dependencies=[Depends(auth.require_project)])
def promote(slug: str, body: PromoteBody) -> dict:
    proj = proj_or_404(slug)
    src = safe_path(proj, body.path)
    if not src.is_file():
        raise HTTPException(status_code=404, detail="source not found")
    if not body.path.startswith("inbox/"):
        raise HTTPException(status_code=400, detail="only inbox/ files can be promoted here")

    dst_rel = "notes/" + Path(body.path).name
    dst = safe_path(proj, dst_rel)
    if dst.exists():
        raise HTTPException(status_code=409, detail=f"target exists: {dst_rel}")

    raw = src.read_text(errors="ignore")
    title = body.title or src.stem.replace("-", " ").replace("_", " ").strip() or src.stem
    tags = ", ".join(body.tags or []) if body.tags else ""
    front = [
        "---",
        f"title: {title}",
    ]
    if tags:
        front.append(f"tags: [{tags}]")
    front.append(f"promoted_from: {body.path}")
    front.append("stage: information")
    front.append("---")
    promoted_text = "\n".join(front) + "\n\n" + raw.lstrip()

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(promoted_text)
    src.unlink()

    search.update_file(proj.vault_dir, src)
    search.update_file(proj.vault_dir, dst)
    versioning.schedule_commit(
        proj.vault_dir,
        reason=f"promote: [data -> information] {body.path} -> {dst_rel}",
    )
    events.emit("fs", {"project": slug, "path": dst_rel, "op": "promoted", "stage": "information"})
    return {"ok": True, "from": body.path, "to": dst_rel}


@router.post("/{slug}/wisdom/synthesise", dependencies=[Depends(auth.require_project)])
def synthesise_wisdom(slug: str) -> dict:
    proj = proj_or_404(slug)
    result = wisdom.synthesise_project(proj.vault_dir, slug)
    if result.produced:
        versioning.schedule_commit(
            proj.vault_dir,
            reason=f"wisdom: synthesised {len(result.produced)} note(s)",
        )
        for path in result.produced:
            events.emit("fs", {"project": slug, "path": path, "op": "created", "stage": "wisdom"})
    return {
        "ok": True,
        "project": result.project,
        "processed": result.processed,
        "produced": result.produced,
        "skipped": result.skipped,
    }
