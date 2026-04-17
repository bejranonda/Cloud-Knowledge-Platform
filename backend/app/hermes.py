"""Hermes Agent bridge: queue + workers + retries.

The watcher (or the /hermes/retrigger endpoint) enqueues Info files.
A pool of worker threads drains the queue, invoking the Hermes CLI and
writing results to `knowledge/`. Failures retry with exponential backoff up
to `MAX_RETRIES`; every state change is emitted on the SSE bus.
"""
from __future__ import annotations

import logging
import queue
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from . import events
from .config import settings

log = logging.getLogger(__name__)

MAX_RETRIES = 3
WORKERS = 2


@dataclass
class HermesJob:
    project: str
    source: str                # relative to vault
    started_ts: float = 0.0
    finished_ts: float = 0.0
    ok: bool = False
    attempts: int = 0
    stderr: str = ""
    produced: list[str] = field(default_factory=list)
    status: str = "queued"     # queued | running | ok | failed


_jobs: deque[HermesJob] = deque(maxlen=500)
_jobs_lock = threading.Lock()
_queue: "queue.Queue[tuple[str, Path, Path]]" = queue.Queue()
_started = False
_start_lock = threading.Lock()


def recent_jobs(limit: int = 50) -> list[HermesJob]:
    with _jobs_lock:
        return list(_jobs)[-limit:][::-1]


def _record(job: HermesJob) -> None:
    with _jobs_lock:
        _jobs.append(job)
    events.emit("hermes", {
        "project": job.project,
        "source": job.source,
        "status": job.status,
        "ok": job.ok,
        "produced": job.produced,
        "attempts": job.attempts,
    })


def enqueue(project_slug: str, vault_dir: Path, source_file: Path) -> None:
    _ensure_workers()
    _queue.put((project_slug, vault_dir, source_file))
    job = HermesJob(
        project=project_slug,
        source=str(source_file.relative_to(vault_dir)) if source_file.is_relative_to(vault_dir) else source_file.name,
        status="queued",
    )
    _record(job)


def _ensure_workers() -> None:
    global _started
    with _start_lock:
        if _started:
            return
        for i in range(WORKERS):
            threading.Thread(target=_worker, name=f"hermes-{i}", daemon=True).start()
        _started = True


def _worker() -> None:
    while True:
        slug, vault_dir, src = _queue.get()
        try:
            _run(slug, vault_dir, src)
        except Exception:
            log.exception("hermes worker error")
        finally:
            _queue.task_done()


def _run(slug: str, vault_dir: Path, src: Path) -> None:
    job = HermesJob(
        project=slug,
        source=str(src.relative_to(vault_dir)) if src.is_relative_to(vault_dir) else src.name,
        started_ts=time.time(),
        status="running",
    )
    _record(job)

    knowledge_dir = vault_dir / "knowledge"
    knowledge_dir.mkdir(exist_ok=True)

    for attempt in range(1, MAX_RETRIES + 1):
        job.attempts = attempt
        if not src.exists():
            job.status = "failed"
            job.stderr = "source file disappeared"
            job.finished_ts = time.time()
            _record(job)
            return

        before = {p.name for p in knowledge_dir.glob("*.md")}
        cmd = [
            settings.hermes_bin,
            "process",
            "--input", str(src),
            "--output-dir", str(knowledge_dir),
            "--project", slug,
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=settings.hermes_timeout_s, check=False,
            )
            rc = proc.returncode
            stderr = proc.stderr[-4000:]
        except subprocess.TimeoutExpired:
            rc, stderr = 124, f"timeout after {settings.hermes_timeout_s}s"
        except FileNotFoundError:
            rc, stderr = 127, f"hermes binary not found: {settings.hermes_bin}"

        job.stderr = stderr
        job.produced = sorted({p.name for p in knowledge_dir.glob("*.md")} - before)
        if rc == 0:
            job.ok = True
            job.status = "ok"
            job.finished_ts = time.time()
            _record(job)
            return
        log.warning("hermes attempt %d/%d failed (rc=%s) for %s", attempt, MAX_RETRIES, rc, src)
        time.sleep(min(2 ** attempt, 10))

    job.status = "failed"
    job.finished_ts = time.time()
    _record(job)
