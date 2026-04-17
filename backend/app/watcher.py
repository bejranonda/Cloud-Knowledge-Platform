"""File system watcher that drives versioning + Hermes dispatch.

One Observer covers all project vaults. Events are routed by the first path
segment under `vaults_root` which is the project slug.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from . import hermes, projects, versioning
from .config import settings

log = logging.getLogger(__name__)

_IGNORED_PREFIXES = (".git", ".obsidian", ".trash", ".registry")


class _Handler(FileSystemEventHandler):
    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        try:
            rel = Path(event.src_path).resolve().relative_to(settings.vaults_root)
        except ValueError:
            return
        parts = rel.parts
        if not parts or any(parts[0].startswith(p) for p in _IGNORED_PREFIXES):
            return
        slug = parts[0]
        if len(parts) > 1 and parts[1].startswith(_IGNORED_PREFIXES):
            return

        proj = projects.get(slug)
        if proj is None:
            return

        versioning.schedule_commit(
            proj.vault_dir, reason=f"sync: {rel.as_posix()} ({event.event_type})"
        )

        # new/modified Info → Hermes
        if (
            event.event_type in ("created", "modified")
            and len(parts) >= 3
            and parts[1] == "inbox"
            and parts[-1].endswith(".md")
        ):
            src = Path(event.src_path)
            threading.Thread(
                target=_run_hermes, args=(proj, src), daemon=True
            ).start()


def _run_hermes(proj: projects.Project, src: Path) -> None:
    if not src.exists():
        return
    job = hermes.dispatch(proj.slug, proj.vault_dir, src)
    if job.ok and job.produced:
        versioning.schedule_commit(
            proj.vault_dir,
            reason=f"hermes: {src.name} -> {', '.join(job.produced)}",
        )


_observer: Observer | None = None


def start() -> None:
    global _observer
    if _observer is not None:
        return
    settings.vaults_root.mkdir(parents=True, exist_ok=True)
    obs = Observer()
    obs.schedule(_Handler(), str(settings.vaults_root), recursive=True)
    obs.start()
    _observer = obs
    log.info("watcher started on %s", settings.vaults_root)


def stop() -> None:
    global _observer
    if _observer is None:
        return
    _observer.stop()
    _observer.join(timeout=5)
    _observer = None
