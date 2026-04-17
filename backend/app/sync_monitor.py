"""CouchDB _changes listener + connection monitor.

Two roles:
1. Materialise CouchDB docs to the on-disk vault so file-based tooling
   (watcher, Hermes, Git) can operate on plain Markdown.
2. Track last-seen timestamps per device so the dashboard can show sync state.
"""
from __future__ import annotations

import base64
import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from . import projects
from .config import settings

log = logging.getLogger(__name__)


@dataclass
class DeviceStatus:
    device: str
    last_seen: float
    last_doc: str = ""
    project: str = ""


_statuses: dict[str, DeviceStatus] = {}
_statuses_lock = threading.Lock()


def device_statuses() -> list[DeviceStatus]:
    with _statuses_lock:
        return sorted(_statuses.values(), key=lambda s: -s.last_seen)


def _record(device: str, project: str, doc_id: str) -> None:
    with _statuses_lock:
        key = f"{project}:{device}"
        _statuses[key] = DeviceStatus(
            device=device, project=project, last_doc=doc_id, last_seen=time.time()
        )


def _materialise(project: projects.Project, doc: dict) -> None:
    """Best-effort: LiveSync stores note path in `path` and body in `data`/`children`."""
    path = doc.get("path") or doc.get("_id")
    if not path or not isinstance(path, str):
        return
    # Guard against path traversal
    rel = Path(path.lstrip("/"))
    if ".." in rel.parts:
        return
    target = project.vault_dir / rel
    if doc.get("deleted"):
        if target.exists():
            target.unlink(missing_ok=True)
        return
    body = doc.get("data")
    if body is None and "children" in doc:
        body = "\n".join(doc.get("children") or [])
    if body is None:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(body, str):
        target.write_text(body)
    elif isinstance(body, bytes):
        target.write_bytes(body)


@dataclass
class _Feed:
    project: projects.Project
    thread: threading.Thread | None = None
    stop_evt: threading.Event = field(default_factory=threading.Event)


_feeds: dict[str, _Feed] = {}
_feeds_lock = threading.Lock()


def _listen(feed: _Feed) -> None:
    proj = feed.project
    db = urllib.parse.quote(proj.slug, safe="")
    since = "now"
    while not feed.stop_evt.is_set():
        url = (
            f"{settings.couchdb_url}/{db}/_changes"
            f"?feed=continuous&include_docs=true&since={since}&heartbeat=30000"
        )
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
                for raw in resp:
                    if feed.stop_evt.is_set():
                        break
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    since = evt.get("seq", since)
                    doc = evt.get("doc") or {}
                    device = doc.get("device") or doc.get("_rev", "unknown").split("-")[0]
                    _record(device, proj.slug, doc.get("_id", ""))
                    _materialise(proj, doc)
        except Exception as e:  # noqa: BLE001
            log.warning("changes feed error for %s: %s", proj.slug, e)
            feed.stop_evt.wait(5)


def start_project(proj: projects.Project) -> None:
    with _feeds_lock:
        if proj.slug in _feeds:
            return
        feed = _Feed(project=proj)
        feed.thread = threading.Thread(target=_listen, args=(feed,), daemon=True)
        feed.thread.start()
        _feeds[proj.slug] = feed


def start_all() -> None:
    for p in projects.list_projects():
        start_project(p)


def stop_all() -> None:
    with _feeds_lock:
        for feed in _feeds.values():
            feed.stop_evt.set()
        _feeds.clear()


# helper for admin UI to (re)create a CouchDB DB
def ensure_couch_db(slug: str) -> bool:
    db = urllib.parse.quote(slug, safe="")
    url = f"{settings.couchdb_url}/{db}"
    try:
        req = urllib.request.Request(url, method="PUT")
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            return resp.status in (201, 202)
    except urllib.error.HTTPError as e:
        return e.code == 412  # already exists
    except Exception:  # noqa: BLE001
        return False


def _b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()
