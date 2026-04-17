"""Process-local SSE broadcaster. Any component can emit; the /api/events
endpoint multicasts to every connected dashboard.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

_subscribers: set[asyncio.Queue[str]] = set()
_loop: asyncio.AbstractEventLoop | None = None


def bind_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def emit(kind: str, payload: dict[str, Any]) -> None:
    """Emit from any thread. No-op if the loop hasn't started yet."""
    if _loop is None:
        return
    data = f"event: {kind}\ndata: {json.dumps(payload, default=str)}\n\n"

    def _fanout() -> None:
        for q in list(_subscribers):
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                pass

    try:
        _loop.call_soon_threadsafe(_fanout)
    except RuntimeError:
        pass


async def stream() -> AsyncIterator[str]:
    q: asyncio.Queue[str] = asyncio.Queue(maxsize=256)
    _subscribers.add(q)
    try:
        yield "event: hello\ndata: {}\n\n"
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=20)
                yield msg
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    finally:
        _subscribers.discard(q)
