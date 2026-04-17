"""FastAPI entrypoint — mounts API, starts watcher + sync feeds, serves frontend."""
from __future__ import annotations

import asyncio
import logging
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import (
    auth,
    events,
    graph,
    hermes,
    obsidian_bridge,
    projects,
    search,
    sync_monitor,
    tags as tags_mod,
    versioning,
    watcher,
    webdav,
)
from .config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("ckp")


@asynccontextmanager
async def lifespan(_: FastAPI):
    events.bind_loop(asyncio.get_running_loop())
    watcher.start()
    sync_monitor.start_all()
    log.info("CKP backend started on %s:%d", settings.host, settings.port)
    try:
        yield
    finally:
        watcher.stop()
        sync_monitor.stop_all()


app = FastAPI(title="Cloud Knowledge Platform", version="0.2.0", lifespan=lifespan)

# WebDAV sync endpoint (Obsidian Remotely Save / any WebDAV client)
app.include_router(webdav.router, prefix="/webdav")


# ---------- models ----------
class NewProject(BaseModel):
    slug: str = Field(min_length=2, max_length=48)
    display_name: str = Field(min_length=1, max_length=100)


class NoteWrite(BaseModel):
    path: str
    content: str


class NoteMove(BaseModel):
    from_: str = Field(alias="from")
    to: str

    class Config:
        populate_by_name = True


# ---------- helpers ----------
def _proj_or_404(slug: str) -> projects.Project:
    p = projects.get(slug)
    if p is None:
        raise HTTPException(status_code=404, detail="project not found")
    return p


def _safe(proj: projects.Project, rel: str) -> Path:
    p = (proj.vault_dir / rel).resolve()
    if not str(p).startswith(str(proj.vault_dir.resolve())):
        raise HTTPException(status_code=400, detail="path outside vault")
    if ".git" in Path(rel).parts:
        raise HTTPException(status_code=400, detail="path in .git")
    return p


# ---------- health + auth probe ----------
@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "version": "0.2.0", "auth_required": auth.enabled()}


# ---------- projects ----------
@app.get("/api/projects")
def list_projects() -> list[dict]:
    return [
        {"slug": p.slug, "display_name": p.display_name} for p in projects.list_projects()
    ]


@app.post("/api/projects", dependencies=[Depends(auth.require)])
def create_project(body: NewProject) -> dict:
    try:
        proj = projects.create(body.slug, body.display_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    sync_monitor.ensure_couch_db(proj.slug)
    sync_monitor.start_project(proj)
    search.reindex(proj.vault_dir)
    events.emit("project", {"slug": proj.slug, "op": "created"})
    return {"slug": proj.slug, "display_name": proj.display_name}


# ---------- sync monitor ----------
@app.get("/api/sync/status")
def sync_status() -> list[dict]:
    return [
        {"device": s.device, "project": s.project, "last_seen": s.last_seen, "last_doc": s.last_doc}
        for s in sync_monitor.device_statuses()
    ]


# ---------- tree + notes ----------
@app.get("/api/projects/{slug}/tree")
def tree(slug: str) -> list[dict]:
    proj = _proj_or_404(slug)
    out = []
    for p in sorted(proj.vault_dir.rglob("*.md")):
        rel = p.relative_to(proj.vault_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue
        st = p.stat()
        out.append({"path": rel.as_posix(), "size": st.st_size, "mtime": int(st.st_mtime)})
    return out


@app.get("/api/projects/{slug}/note")
def read_note(slug: str, path: str) -> PlainTextResponse:
    proj = _proj_or_404(slug)
    p = _safe(proj, path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return PlainTextResponse(p.read_text())


@app.put("/api/projects/{slug}/note", dependencies=[Depends(auth.require)])
def write_note(slug: str, body: NoteWrite) -> dict:
    proj = _proj_or_404(slug)
    p = _safe(proj, body.path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body.content)
    search.update_file(proj.vault_dir, p)
    versioning.schedule_commit(proj.vault_dir, reason=f"manual: {body.path} via web-app")
    events.emit("fs", {"project": slug, "path": body.path, "op": "modified"})
    return {"ok": True, "path": body.path}


@app.delete("/api/projects/{slug}/note", dependencies=[Depends(auth.require)])
def delete_note(slug: str, path: str) -> dict:
    proj = _proj_or_404(slug)
    p = _safe(proj, path)
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


@app.post("/api/projects/{slug}/note/move", dependencies=[Depends(auth.require)])
def move_note(slug: str, body: NoteMove) -> dict:
    proj = _proj_or_404(slug)
    src = _safe(proj, body.from_)
    dst = _safe(proj, body.to)
    if not src.exists():
        raise HTTPException(status_code=404, detail="source not found")
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    search.update_file(proj.vault_dir, src)
    search.update_file(proj.vault_dir, dst)
    versioning.schedule_commit(proj.vault_dir, reason=f"manual: move {body.from_} -> {body.to}")
    events.emit("fs", {"project": slug, "path": body.to, "op": "moved"})
    return {"ok": True}


# ---------- graph + backlinks ----------
@app.get("/api/projects/{slug}/graph")
def project_graph(slug: str) -> dict:
    return graph.build(_proj_or_404(slug).vault_dir)


@app.get("/api/projects/{slug}/backlinks")
def backlinks(slug: str, path: str) -> list[dict]:
    return graph.backlinks(_proj_or_404(slug).vault_dir, path)


# ---------- search + tags ----------
@app.get("/api/projects/{slug}/search")
def project_search(slug: str, q: str, limit: int = 20) -> list[dict]:
    proj = _proj_or_404(slug)
    hits = search.query(proj.vault_dir, q, limit=limit)
    return [{**h, "snippet": search.snippet(proj.vault_dir, h["path"], q)} for h in hits]


@app.get("/api/projects/{slug}/tags")
def project_tags(slug: str) -> dict:
    return tags_mod.build_index(_proj_or_404(slug).vault_dir)


# ---------- history ----------
@app.get("/api/projects/{slug}/history")
def history(slug: str, limit: int = 50) -> list[dict]:
    return versioning.history(_proj_or_404(slug).vault_dir, limit=limit)


@app.get("/api/projects/{slug}/history/file")
def file_history(slug: str, path: str, limit: int = 50) -> list[dict]:
    return versioning.file_history(_proj_or_404(slug).vault_dir, path, limit=limit)


@app.get("/api/projects/{slug}/history/show")
def history_show(slug: str, commit: str, path: str) -> PlainTextResponse:
    content = versioning.show_at(_proj_or_404(slug).vault_dir, commit, path)
    if content is None:
        raise HTTPException(status_code=404, detail="not in commit")
    return PlainTextResponse(content)


@app.get("/api/projects/{slug}/history/diff")
def history_diff(slug: str, commit: str, path: str | None = None) -> PlainTextResponse:
    return PlainTextResponse(versioning.diff(_proj_or_404(slug).vault_dir, commit, path))


@app.post("/api/projects/{slug}/history/restore", dependencies=[Depends(auth.require)])
def history_restore(slug: str, commit: str, path: str) -> dict:
    proj = _proj_or_404(slug)
    ok = versioning.restore(proj.vault_dir, commit, path)
    if not ok:
        raise HTTPException(status_code=404, detail="not in commit")
    search.update_file(proj.vault_dir, proj.vault_dir / path)
    events.emit("fs", {"project": slug, "path": path, "op": "restored"})
    return {"ok": True}


# ---------- hermes ----------
@app.get("/api/hermes/jobs")
def hermes_jobs(limit: int = 50) -> list[dict]:
    return [
        {
            "project": j.project,
            "source": j.source,
            "started_ts": j.started_ts,
            "finished_ts": j.finished_ts,
            "ok": j.ok,
            "attempts": j.attempts,
            "status": j.status,
            "produced": j.produced,
            "stderr": j.stderr,
        }
        for j in hermes.recent_jobs(limit=limit)
    ]


@app.post("/api/projects/{slug}/hermes/retrigger", dependencies=[Depends(auth.require)])
def hermes_retrigger(slug: str, path: str) -> dict:
    proj = _proj_or_404(slug)
    src = _safe(proj, path)
    if not src.is_file():
        raise HTTPException(status_code=404, detail="not found")
    hermes.enqueue(slug, proj.vault_dir, src)
    return {"ok": True}


# ---------- obsidian bridge ----------
@app.get("/api/projects/{slug}/obsidian/summary")
def obsidian_summary(slug: str) -> dict:
    _proj_or_404(slug)
    try:
        return obsidian_bridge.summary(slug)
    except KeyError:
        raise HTTPException(status_code=404, detail="project not found")


@app.get("/api/projects/{slug}/obsidian/starred")
def obsidian_starred(slug: str) -> list[dict]:
    _proj_or_404(slug)
    return obsidian_bridge.starred(slug)


@app.get("/api/projects/{slug}/obsidian/plugins")
def obsidian_plugins(slug: str) -> dict:
    _proj_or_404(slug)
    return obsidian_bridge.plugins(slug)


@app.get("/api/projects/{slug}/obsidian/recent")
def obsidian_recent(slug: str, limit: int = 20) -> list[str]:
    _proj_or_404(slug)
    return obsidian_bridge.recent_files(slug, limit=limit)


# ---------- SSE ----------
@app.get("/api/events")
async def sse() -> StreamingResponse:
    return StreamingResponse(events.stream(), media_type="text/event-stream")


# ---------- frontend ----------
if settings.frontend_dir.is_dir():
    app.mount("/ui", StaticFiles(directory=str(settings.frontend_dir), html=True), name="ui")

    @app.get("/")
    def root() -> FileResponse:
        return FileResponse(settings.frontend_dir / "index.html")
