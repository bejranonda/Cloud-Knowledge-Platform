"""Runtime configuration (env-driven)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("CKP_HOST", "0.0.0.0")
    port: int = int(os.getenv("CKP_PORT", "8787"))

    vaults_root: Path = Path(os.getenv("CKP_VAULTS_ROOT", "./vaults")).resolve()

    couchdb_url: str = os.getenv("CKP_COUCHDB_URL", "http://admin:admin@127.0.0.1:5984")

    hermes_bin: str = os.getenv("CKP_HERMES_BIN", "hermes-agent")
    hermes_timeout_s: int = int(os.getenv("CKP_HERMES_TIMEOUT", "120"))

    commit_debounce_s: float = float(os.getenv("CKP_COMMIT_DEBOUNCE", "2.0"))
    git_author_name: str = os.getenv("CKP_GIT_AUTHOR", "sync-bot")
    git_author_email: str = os.getenv("CKP_GIT_EMAIL", "sync@platform.local")

    frontend_dir: Path = Path(__file__).resolve().parent.parent.parent / "frontend"


settings = Settings()
settings.vaults_root.mkdir(parents=True, exist_ok=True)
