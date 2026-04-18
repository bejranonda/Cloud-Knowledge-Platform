"""/api/projects/{slug}/attachments — upload + serve binary files.

Uploads land under `<vault>/attachments/` so they stay in the vault (sync'd,
versioned, visible to Obsidian). Large files beyond `MAX_UPLOAD_BYTES` are
rejected; the recommended escape hatch is a symlink to an object store.
"""
from __future__ import annotations

import mimetypes
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .. import auth, events, search, versioning
from ..util import proj_or_404, safe_path

router = APIRouter(prefix="/api/projects", tags=["attachments"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
_SAFE_NAME = re.compile(r"[^a-zA-Z0-9._\- ]+")


def _sanitise(name: str) -> str:
    name = Path(name).name  # strip directories
    cleaned = _SAFE_NAME.sub("_", name).strip()
    return cleaned or "upload"


@router.post("/{slug}/attachments", dependencies=[Depends(auth.require_project)])
async def upload_attachment(slug: str, file: UploadFile = File(...)) -> dict:
    proj = proj_or_404(slug)
    att_dir = proj.vault_dir / "attachments"
    att_dir.mkdir(exist_ok=True)

    name = _sanitise(file.filename or "upload")
    target = safe_path(proj, f"attachments/{name}")

    # Avoid clobber: append -1, -2, ... if exists. Re-validate each candidate
    # through safe_path so the target can never drift outside the vault.
    stem, suffix = target.stem, target.suffix
    n = 1
    while target.exists():
        target = safe_path(proj, f"attachments/{stem}-{n}{suffix}")
        n += 1

    total = 0
    with target.open("wb") as fh:
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                fh.close()
                target.unlink(missing_ok=True)
                raise HTTPException(413, f"file exceeds {MAX_UPLOAD_BYTES} bytes")
            fh.write(chunk)

    rel = target.relative_to(proj.vault_dir).as_posix()
    versioning.schedule_commit(proj.vault_dir, reason=f"upload: {rel}")
    search.update_file(proj.vault_dir, target)  # no-op for non-md; cheap
    events.emit("fs", {"project": slug, "path": rel, "op": "created"})
    return {"ok": True, "path": rel, "size": total}


@router.get("/{slug}/attachments/{name:path}")
def get_attachment(slug: str, name: str) -> FileResponse:
    proj = proj_or_404(slug)
    p = safe_path(proj, f"attachments/{name}")
    if not p.is_file():
        raise HTTPException(404, "not found")
    mime, _ = mimetypes.guess_type(p.name)
    return FileResponse(p, media_type=mime or "application/octet-stream")
