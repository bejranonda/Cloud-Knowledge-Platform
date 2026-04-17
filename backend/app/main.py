"""FastAPI entrypoint — starts watcher + sync feeds, mounts routers + frontend."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import auth, events, sync_monitor, watcher, webdav
from .config import settings
from .routes import (
    attachments_routes,
    credentials_routes,
    hermes_routes,
    history_routes,
    notes_routes,
    obsidian_routes,
    projects_routes,
    search_routes,
    sync_routes,
)

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


app = FastAPI(title="Cloud Knowledge Platform", version="0.3.0", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "version": "0.3.0", "auth_required": auth.admin_enabled()}


# API routers
for r in (
    projects_routes.router,
    notes_routes.router,
    history_routes.router,
    search_routes.router,
    obsidian_routes.router,
    hermes_routes.router,
    sync_routes.router,
    attachments_routes.router,
    credentials_routes.router,
):
    app.include_router(r)

# WebDAV at /webdav/{slug}/...
app.include_router(webdav.router, prefix="/webdav")


# Frontend
if settings.frontend_dir.is_dir():
    app.mount("/ui", StaticFiles(directory=str(settings.frontend_dir), html=True), name="ui")

    @app.get("/")
    def root() -> FileResponse:
        return FileResponse(settings.frontend_dir / "index.html")
