"""/api/sync/status and /api/events (SSE)."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from .. import events, sync_monitor

router = APIRouter(prefix="/api", tags=["sync"])


@router.get("/sync/status")
def sync_status() -> list[dict]:
    return [
        {"device": s.device, "project": s.project, "last_seen": s.last_seen, "last_doc": s.last_doc}
        for s in sync_monitor.device_statuses()
    ]


@router.get("/events")
async def sse() -> StreamingResponse:
    return StreamingResponse(events.stream(), media_type="text/event-stream")
