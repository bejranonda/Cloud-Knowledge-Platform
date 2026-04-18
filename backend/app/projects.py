"""Multi-project registry. Each project = CouchDB DB + vault dir + Git repo."""
from __future__ import annotations

import json
import re
import subprocess
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import settings

# Slug: 2–49 chars (first char required, then up to 48 more). Keep in sync
# with NewProject.max_length in routes/projects_routes.py (49).
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}$")
_REGISTRY = settings.vaults_root / ".registry.json"
_CREATE_LOCK = threading.Lock()


@dataclass
class Project:
    slug: str
    display_name: str

    @property
    def vault_dir(self) -> Path:
        return settings.vaults_root / self.slug

    @property
    def inbox_dir(self) -> Path:
        return self.vault_dir / "inbox"

    @property
    def knowledge_dir(self) -> Path:
        return self.vault_dir / "knowledge"

    @property
    def notes_dir(self) -> Path:
        return self.vault_dir / "notes"

    @property
    def wisdom_dir(self) -> Path:
        return self.vault_dir / "wisdom"


def _load() -> dict[str, Project]:
    if not _REGISTRY.exists():
        return {}
    raw = json.loads(_REGISTRY.read_text())
    return {s: Project(**p) for s, p in raw.items()}


def _save(projects: dict[str, Project]) -> None:
    _REGISTRY.write_text(
        json.dumps({s: asdict(p) for s, p in projects.items()}, indent=2)
    )


def list_projects() -> list[Project]:
    return list(_load().values())


def get(slug: str) -> Project | None:
    return _load().get(slug)


def create(slug: str, display_name: str) -> Project:
    if not _SLUG_RE.match(slug):
        raise ValueError(f"invalid slug: {slug!r}")
    # Serialise the whole read-modify-write so two concurrent requests can't
    # both pass the existence check, create the same vault, and race on
    # writing the registry.
    with _CREATE_LOCK:
        projects = _load()
        if slug in projects:
            raise ValueError(f"project exists: {slug}")

        proj = Project(slug=slug, display_name=display_name)
        for d in (
            proj.vault_dir,
            proj.inbox_dir,
            proj.knowledge_dir,
            proj.notes_dir,
            proj.wisdom_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

        # init git repo if missing
        if not (proj.vault_dir / ".git").exists():
            subprocess.run(
                ["git", "init", "-q", "-b", "main"], cwd=proj.vault_dir, check=True
            )
            subprocess.run(
                ["git", "config", "user.name", settings.git_author_name],
                cwd=proj.vault_dir,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", settings.git_author_email],
                cwd=proj.vault_dir,
                check=True,
            )
            readme = proj.vault_dir / "README.md"
            readme.write_text(
                f"# {display_name}\n\n"
                "DIKW-T pyramid: inbox/ (Data) → notes/ (Information) → "
                "knowledge/ (Knowledge, Hermes) → wisdom/ (Wisdom + Time).\n"
            )
            subprocess.run(["git", "add", "-A"], cwd=proj.vault_dir, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", f"init: {slug}"],
                cwd=proj.vault_dir,
                check=True,
            )

        projects[slug] = proj
        _save(projects)
        return proj
