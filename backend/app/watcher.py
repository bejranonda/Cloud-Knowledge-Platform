"""File system watcher — drives versioning, search reindex, and Hermes queue."""
from __future__ import annotations

import logging
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from . import events, hermes, projects, search, versioning
from .config import settings

log = logging.getLogger(__name__)

_IGNORED = (".git", ".obsidian", ".trash", ".registry")
# Only react to events that mutate content. Newer watchdog emits opened /
# closed / closed_no_write; reacting to those would create a feedback loop
# because search.update_file() reads the file, which emits another "opened".
_MUTATING = {"created", "modified", "deleted", "moved"}


class _Handler(FileSystemEventHandler):
    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if event.event_type not in _MUTATING:
            return
        try:
            rel = Path(event.src_path).resolve().relative_to(settings.vaults_root)
        except ValueError:
            return
        parts = rel.parts
        if not parts or parts[0].startswith(_IGNORED):
            return
        slug = parts[0]
        if len(parts) > 1 and parts[1].startswith(_IGNORED):
            return

        proj = projects.get(slug)
        if proj is None:
            return

        abs_path = Path(event.src_path)

        if str(abs_path).endswith(".md"):
            search.update_file(proj.vault_dir, abs_path)

        versioning.schedule_commit(
            proj.vault_dir, reason=f"sync: {rel.as_posix()} ({event.event_type})"
        )
        events.emit("fs", {
            "project": slug, "path": rel.relative_to(slug).as_posix(),
            "op": event.event_type,
        })

        if (
            event.event_type in ("created", "modified")
            and len(parts) >= 3
            and parts[1] == "inbox"
            and parts[-1].endswith(".md")
        ):
            hermes.enqueue(slug, proj.vault_dir, abs_path)


_observer: Observer | None = None


def start() -> None:
    global _observer
    if _observer is not None:
        return
    settings.vaults_root.mkdir(parents=True, exist_ok=True)
    for p in projects.list_projects():
        search.reindex(p.vault_dir)
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
