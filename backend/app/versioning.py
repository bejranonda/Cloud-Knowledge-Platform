"""Debounced per-project Git committer.

Commits are serialised per project: each project has a single worker thread
consuming a queue of change events, with a coalescing debounce window.
"""
from __future__ import annotations

import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import settings

log = logging.getLogger(__name__)


@dataclass
class _ProjectQueue:
    last_event_ts: float = 0.0
    pending_reason: str = ""
    lock: threading.Lock = field(default_factory=threading.Lock)
    worker: threading.Thread | None = None


_queues: dict[str, _ProjectQueue] = {}
_registry_lock = threading.Lock()


def schedule_commit(vault_dir: Path, reason: str) -> None:
    """Request a commit. Coalesces events within the debounce window."""
    key = str(vault_dir)
    with _registry_lock:
        q = _queues.setdefault(key, _ProjectQueue())
    with q.lock:
        q.last_event_ts = time.monotonic()
        q.pending_reason = reason or q.pending_reason
        if q.worker is None or not q.worker.is_alive():
            q.worker = threading.Thread(
                target=_run_worker, args=(vault_dir, q), daemon=True
            )
            q.worker.start()


def _run_worker(vault_dir: Path, q: _ProjectQueue) -> None:
    debounce = settings.commit_debounce_s
    while True:
        with q.lock:
            wait = debounce - (time.monotonic() - q.last_event_ts)
        if wait > 0:
            time.sleep(wait)
            continue
        with q.lock:
            reason = q.pending_reason
            q.pending_reason = ""
        try:
            _do_commit(vault_dir, reason)
        except Exception:
            log.exception("commit failed for %s", vault_dir)
        with q.lock:
            if q.pending_reason:
                continue
            # no new work
            q.worker = None
            return


def _do_commit(vault_dir: Path, reason: str) -> None:
    if not (vault_dir / ".git").exists():
        log.warning("no .git in %s, skipping commit", vault_dir)
        return
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=vault_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    if not status.stdout.strip():
        return
    subprocess.run(["git", "add", "-A"], cwd=vault_dir, check=True)
    msg = reason or f"sync @ {int(time.time())}"
    subprocess.run(
        ["git", "commit", "-q", "-m", msg],
        cwd=vault_dir,
        check=True,
    )
    log.info("committed %s: %s", vault_dir.name, msg)


def history(vault_dir: Path, limit: int = 50) -> list[dict]:
    """Return recent commits as [{hash, ts, msg, author}]."""
    if not (vault_dir / ".git").exists():
        return []
    fmt = "%H%x1f%ct%x1f%an%x1f%s"
    out = subprocess.run(
        ["git", "log", f"-n{limit}", f"--pretty=format:{fmt}"],
        cwd=vault_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    commits = []
    for line in out.stdout.splitlines():
        h, ts, author, msg = line.split("\x1f", 3)
        commits.append({"hash": h, "ts": int(ts), "author": author, "msg": msg})
    return commits


def file_history(vault_dir: Path, rel_path: str, limit: int = 50) -> list[dict]:
    """History restricted to one file."""
    if not (vault_dir / ".git").exists():
        return []
    fmt = "%H%x1f%ct%x1f%an%x1f%s"
    out = subprocess.run(
        ["git", "log", f"-n{limit}", f"--pretty=format:{fmt}", "--", rel_path],
        cwd=vault_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    commits = []
    for line in out.stdout.splitlines():
        if not line:
            continue
        h, ts, author, msg = line.split("\x1f", 3)
        commits.append({"hash": h, "ts": int(ts), "author": author, "msg": msg})
    return commits


def diff(vault_dir: Path, commit: str, rel_path: str | None = None) -> str:
    """Unified diff for one commit, optionally scoped to a path."""
    cmd = ["git", "show", "--format=", "--no-color", commit]
    if rel_path:
        cmd += ["--", rel_path]
    out = subprocess.run(cmd, cwd=vault_dir, check=False, capture_output=True, text=True)
    return out.stdout


def restore(vault_dir: Path, commit: str, rel_path: str) -> bool:
    """Restore `rel_path` to its state at `commit` as a new commit. Returns True on success."""
    content = show_at(vault_dir, commit, rel_path)
    if content is None:
        return False
    target = vault_dir / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    subprocess.run(["git", "add", "--", rel_path], cwd=vault_dir, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", f"restore: {rel_path} -> {commit[:8]}"],
        cwd=vault_dir,
        check=False,
    )
    return True


def show_at(vault_dir: Path, commit: str, rel_path: str) -> str | None:
    """Return file contents at a given commit, or None if absent."""
    try:
        out = subprocess.run(
            ["git", "show", f"{commit}:{rel_path}"],
            cwd=vault_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        return out.stdout
    except subprocess.CalledProcessError:
        return None
