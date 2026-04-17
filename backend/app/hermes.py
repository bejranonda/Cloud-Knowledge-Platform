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
from dataclasses import asdict, dataclass, field
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


_MAX_JOBS = 500
_jobs: dict[str, HermesJob] = {}       # keyed by id
_job_order: list[str] = []             # insertion order
_jobs_lock = threading.Lock()
_queue: "queue.Queue[tuple[str, str, Path, Path]]" = queue.Queue()
_started = False
_start_lock = threading.Lock()


def _job_id(slug: str, src: Path, started_ts: float) -> str:
    return f"{slug}:{src.name}:{started_ts:.3f}"


def recent_jobs(limit: int = 50) -> list[HermesJob]:
    """Return an ordered snapshot (newest first) of the last *limit* jobs."""
    with _jobs_lock:
        ids = _job_order[-limit:][::-1]
        return [HermesJob(**asdict(_jobs[i])) for i in ids if i in _jobs]


def _record(job_id: str, job: HermesJob) -> None:
    with _jobs_lock:
        if job_id not in _jobs:
            _job_order.append(job_id)
            if len(_job_order) > _MAX_JOBS:
                oldest = _job_order.pop(0)
                _jobs.pop(oldest, None)
        _jobs[job_id] = HermesJob(**asdict(job))  # snapshot
    events.emit("hermes", {
        "id": job_id,
        "project": job.project,
        "source": job.source,
        "status": job.status,
        "ok": job.ok,
        "produced": list(job.produced),
        "attempts": job.attempts,
    })


def enqueue(project_slug: str, vault_dir: Path, source_file: Path) -> None:
    _ensure_workers()
    started = time.time()
    jid = _job_id(project_slug, source_file, started)
    job = HermesJob(
        project=project_slug,
        source=str(source_file.relative_to(vault_dir)) if source_file.is_relative_to(vault_dir) else source_file.name,
        started_ts=started,
        status="queued",
    )
    _record(jid, job)
    _queue.put((jid, project_slug, vault_dir, source_file))


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
        jid, slug, vault_dir, src = _queue.get()
        try:
            _run(jid, slug, vault_dir, src)
        except Exception:
            log.exception("hermes worker error")
        finally:
            _queue.task_done()


def _run(jid: str, slug: str, vault_dir: Path, src: Path) -> None:
    with _jobs_lock:
        existing = _jobs.get(jid)
    job = HermesJob(**asdict(existing)) if existing else HermesJob(
        project=slug,
        source=str(src.relative_to(vault_dir)) if src.is_relative_to(vault_dir) else src.name,
        started_ts=time.time(),
    )
    job.status = "running"
    _record(jid, job)

    knowledge_dir = vault_dir / "knowledge"
    knowledge_dir.mkdir(exist_ok=True)

    for attempt in range(1, MAX_RETRIES + 1):
        job.attempts = attempt
        if not src.exists():
            job.status = "failed"
            job.stderr = "source file disappeared"
            job.finished_ts = time.time()
            _record(jid, job)
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
            _record(jid, job)
            return
        log.warning("hermes attempt %d/%d failed (rc=%s) for %s", attempt, MAX_RETRIES, rc, src)
        time.sleep(min(2 ** attempt, 10))

    job.status = "failed"
    job.finished_ts = time.time()
    _record(jid, job)
