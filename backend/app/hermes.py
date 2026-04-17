"""Bridge to the pre-installed Hermes Agent.

Hermes converts raw `inbox/*.md` Info into structured `knowledge/*.md` files.
Invocation is intentionally thin so the exact CLI can be tuned per deployment.
"""
from __future__ import annotations

import logging
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from .config import settings

log = logging.getLogger(__name__)


@dataclass
class HermesJob:
    project: str
    source: str
    started_ts: float
    finished_ts: float = 0.0
    ok: bool = False
    stderr: str = ""
    produced: list[str] = field(default_factory=list)


_jobs: deque[HermesJob] = deque(maxlen=200)
_jobs_lock = threading.Lock()


def recent_jobs(limit: int = 50) -> list[HermesJob]:
    with _jobs_lock:
        return list(_jobs)[-limit:][::-1]


def dispatch(project_slug: str, vault_dir: Path, source_file: Path) -> HermesJob:
    """Run Hermes on one Info file. Blocking; call from a worker thread."""
    job = HermesJob(
        project=project_slug,
        source=str(source_file.relative_to(vault_dir)),
        started_ts=time.time(),
    )
    knowledge_dir = vault_dir / "knowledge"
    knowledge_dir.mkdir(exist_ok=True)

    cmd = [
        settings.hermes_bin,
        "process",
        "--input",
        str(source_file),
        "--output-dir",
        str(knowledge_dir),
        "--project",
        project_slug,
    ]
    log.info("hermes dispatch: %s", " ".join(cmd))

    before = {p.name for p in knowledge_dir.glob("*.md")}
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=settings.hermes_timeout_s,
            check=False,
        )
        job.ok = proc.returncode == 0
        job.stderr = proc.stderr[-4000:]
    except subprocess.TimeoutExpired:
        job.ok = False
        job.stderr = f"timeout after {settings.hermes_timeout_s}s"
    except FileNotFoundError:
        job.ok = False
        job.stderr = f"hermes binary not found: {settings.hermes_bin}"

    after = {p.name for p in knowledge_dir.glob("*.md")}
    job.produced = sorted(after - before)
    job.finished_ts = time.time()

    with _jobs_lock:
        _jobs.append(job)
    return job
