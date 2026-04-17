"""Session-level fixtures: env setup, app import, TestClient."""
from __future__ import annotations

import os
import pytest

# ── env vars MUST be set before the app modules are imported ──────────────────


def pytest_configure(config):
    """Called very early — before collection and before any import of app."""
    # These are set here so that even top-level module code in app/* (which
    # runs at import time) sees the right values.
    os.environ.setdefault("CKP_ADMIN_TOKEN", "test-admin-token")
    os.environ.setdefault("CKP_COUCHDB_URL", "http://127.0.0.1:1")
    os.environ.setdefault("CKP_HERMES_BIN", "/bin/true")
    # CKP_VAULTS_ROOT is patched per-session in the fixture below; we set a
    # placeholder here so Settings() doesn't fail if it's imported before the
    # fixture runs.  The fixture will override it before the first TestClient.


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    """Session-scoped FastAPI TestClient with an isolated vault root."""
    vault_root = tmp_path_factory.mktemp("vaults")
    os.environ["CKP_VAULTS_ROOT"] = str(vault_root)
    os.environ["CKP_ADMIN_TOKEN"] = "test-admin-token"
    os.environ["CKP_COUCHDB_URL"] = "http://127.0.0.1:1"
    os.environ["CKP_HERMES_BIN"] = "/bin/true"

    # Import app AFTER env vars are set.
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        yield c
