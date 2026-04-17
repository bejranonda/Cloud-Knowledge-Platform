"""FastAPI entrypoint — mounts API, starts watcher + sync feeds, serves frontend."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import graph, hermes, projects, sync_monitor, versioning, watcher
from .config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ckp")


@asynccontextmanager
async def lifespan(_: FastAPI):
    watcher.start()
    sync_monitor.start_all()
    log.info("CKP backend started on %s:%d", settings.host, settings.port)
    try:
        yield
    finally:
        watcher.stop()
        sync_monitor.stop_all()


app = FastAPI(title="Cloud Knowledge Platform", version="0.1.0", lifespan=lifespan)


# ---------- models ----------
class NewProject(BaseModel):
    slug: str = Field(min_length=2, max_length=48)
    display_name: str = Field(min_length=1, max_length=100)


class NoteWrite(BaseModel):
    path: str
    content: str


# ---------- helpers ----------
def _proj_or_404(slug: str) -> projects.Project:
    p = projects.get(slug)
    if p is None:
        raise HTTPException(status_code=404, detail="project not found")
    return p


def _safe_path(proj: projects.Project, rel: str) -> Path:
    p = (proj.vault_dir / rel).resolve()
    if not str(p).startswith(str(proj.vault_dir.resolve())):
        raise HTTPException(status_code=400, detail="path outside vault")
    return p


# ---------- routes ----------
@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "version": "0.1.0"}


@app.get("/api/projects")
def list_projects() -> list[dict]:
    return [
        {"slug": p.slug, "display_name": p.display_name} for p in projects.list_projects()
    ]


@app.post("/api/projects")
def create_project(body: NewProject) -> dict:
    try:
        proj = projects.create(body.slug, body.display_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    sync_monitor.ensure_couch_db(proj.slug)
    sync_monitor.start_project(proj)
    return {"slug": proj.slug, "display_name": proj.display_name}


@app.get("/api/sync/status")
def sync_status() -> list[dict]:
    return [
        {"device": s.device, "project": s.project, "last_seen": s.last_seen, "last_doc": s.last_doc}
        for s in sync_monitor.device_statuses()
    ]


@app.get("/api/projects/{slug}/tree")
def tree(slug: str) -> list[dict]:
    proj = _proj_or_404(slug)
    out = []
    for p in sorted(proj.vault_dir.rglob("*.md")):
        if any(part.startswith(".") for part in p.relative_to(proj.vault_dir).parts):
            continue
        out.append(
            {
                "path": p.relative_to(proj.vault_dir).as_posix(),
                "size": p.stat().st_size,
                "mtime": int(p.stat().st_mtime),
            }
        )
    return out


@app.get("/api/projects/{slug}/note")
def read_note(slug: str, path: str) -> PlainTextResponse:
    proj = _proj_or_404(slug)
    p = _safe_path(proj, path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return PlainTextResponse(p.read_text())


@app.put("/api/projects/{slug}/note")
def write_note(slug: str, body: NoteWrite) -> dict:
    proj = _proj_or_404(slug)
    p = _safe_path(proj, body.path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body.content)
    versioning.schedule_commit(proj.vault_dir, reason=f"manual: {body.path} via web-app")
    return {"ok": True, "path": body.path}


@app.get("/api/projects/{slug}/graph")
def project_graph(slug: str) -> dict:
    return graph.build(_proj_or_404(slug).vault_dir)


@app.get("/api/projects/{slug}/history")
def history(slug: str, limit: int = 50) -> list[dict]:
    return versioning.history(_proj_or_404(slug).vault_dir, limit=limit)


@app.get("/api/projects/{slug}/history/show")
def history_show(slug: str, commit: str, path: str) -> PlainTextResponse:
    content = versioning.show_at(_proj_or_404(slug).vault_dir, commit, path)
    if content is None:
        raise HTTPException(status_code=404, detail="not in commit")
    return PlainTextResponse(content)


@app.get("/api/hermes/jobs")
def hermes_jobs(limit: int = 50) -> list[dict]:
    return [
        {
            "project": j.project,
            "source": j.source,
            "started_ts": j.started_ts,
            "finished_ts": j.finished_ts,
            "ok": j.ok,
            "produced": j.produced,
            "stderr": j.stderr,
        }
        for j in hermes.recent_jobs(limit=limit)
    ]


# ---------- frontend ----------
if settings.frontend_dir.is_dir():
    app.mount("/ui", StaticFiles(directory=str(settings.frontend_dir), html=True), name="ui")

    @app.get("/")
    def root() -> FileResponse:
        return FileResponse(settings.frontend_dir / "index.html")
