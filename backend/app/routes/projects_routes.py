"""/api/projects — list and create."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import auth, events, projects, search, sync_monitor

router = APIRouter(prefix="/api", tags=["projects"])


class NewProject(BaseModel):
    slug: str = Field(min_length=2, max_length=49)
    display_name: str = Field(min_length=1, max_length=100)


@router.get("/projects")
def list_projects() -> list[dict]:
    return [
        {"slug": p.slug, "display_name": p.display_name} for p in projects.list_projects()
    ]


@router.post("/projects", dependencies=[Depends(auth.require_admin)])
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
