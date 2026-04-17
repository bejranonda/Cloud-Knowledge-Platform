"""Auth with two tiers:

- **Admin token** (env `CKP_ADMIN_TOKEN`): full access. Used to bootstrap
  projects and issue per-project credentials. Optional — if unset, auth is
  disabled globally (dev mode).
- **Per-project tokens**: issued via `/api/projects/{slug}/credentials`,
  persisted in `<vaults_root>/.credentials.json`. Each token grants write
  access to exactly one project (API + WebDAV).

Request auth surface:
- API routes: `Authorization: Bearer <token>` — token may be the admin token
  or a project token matching the requested slug.
- WebDAV: `Authorization: Basic <b64>` where password == admin or project
  token. Username is ignored. Bearer is also accepted.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import threading
from pathlib import Path

from fastapi import Header, HTTPException, Request, status

from .config import settings

_ADMIN = os.getenv("CKP_ADMIN_TOKEN", "").strip()
_CRED_FILE = settings.vaults_root / ".credentials.json"
_lock = threading.Lock()


def admin_enabled() -> bool:
    return bool(_ADMIN)


def _load() -> dict[str, list[str]]:
    if not _CRED_FILE.exists():
        return {}
    try:
        return json.loads(_CRED_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save(db: dict[str, list[str]]) -> None:
    _CRED_FILE.write_text(json.dumps(db, indent=2))


# ---------- token management ----------
def list_tokens(slug: str) -> list[str]:
    """Return masked tokens (first 6 + ellipsis) for display."""
    with _lock:
        return [f"{t[:6]}…{t[-4:]}" for t in _load().get(slug, [])]


def issue_token(slug: str) -> str:
    with _lock:
        db = _load()
        tok = "ckp_" + secrets.token_urlsafe(32)
        db.setdefault(slug, []).append(tok)
        _save(db)
        return tok


def revoke_token(slug: str, prefix: str) -> bool:
    """Revoke first token whose prefix matches (first 6 chars)."""
    with _lock:
        db = _load()
        toks = db.get(slug, [])
        for i, t in enumerate(toks):
            if t.startswith(prefix):
                del toks[i]
                _save(db)
                return True
        return False


def _token_matches_project(slug: str, given: str) -> bool:
    with _lock:
        return any(secrets.compare_digest(t, given) for t in _load().get(slug, []))


def _is_admin(given: str) -> bool:
    return bool(_ADMIN) and secrets.compare_digest(given, _ADMIN)


# ---------- request-time checks ----------
def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2:
        return None
    scheme, value = parts[0].lower(), parts[1].strip()
    if scheme == "bearer":
        return value
    if scheme == "basic":
        try:
            decoded = base64.b64decode(value).decode()
        except (ValueError, UnicodeDecodeError):
            return None
        # username:password — we only care about password
        return decoded.split(":", 1)[1] if ":" in decoded else decoded
    return None


def require_admin(authorization: str | None = Header(default=None)) -> None:
    if not _ADMIN:
        return  # dev mode
    tok = _extract_bearer(authorization)
    if not tok or not _is_admin(tok):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "admin auth required")


def require_project(request: Request, authorization: str | None = Header(default=None)) -> None:
    """Allow either admin token OR a project-scoped token whose slug matches
    the `{slug}` path parameter of the request."""
    if not _ADMIN and not _load():
        return  # dev mode, nothing configured
    tok = _extract_bearer(authorization)
    if not tok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    if _is_admin(tok):
        return
    slug = request.path_params.get("slug")
    if slug and _token_matches_project(slug, tok):
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "token not valid for this project")


# Back-compat alias; WebDAV file imports this name.
def require(authorization: str | None = Header(default=None)) -> None:
    """Any valid token (admin or any project). Used by WebDAV where the slug
    is enforced inside the handler."""
    if not _ADMIN and not _load():
        return
    tok = _extract_bearer(authorization)
    if not tok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    if _is_admin(tok):
        return
    with _lock:
        for toks in _load().values():
            if any(secrets.compare_digest(t, tok) for t in toks):
                return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "bad token")


def enabled() -> bool:
    """Legacy name used by webdav.py."""
    return bool(_ADMIN) or bool(_load())


def require_for_project(slug: str, authorization: str | None) -> None:
    """Helper for WebDAV handler: verify token is admin or project-scoped."""
    if not enabled():
        return
    tok = _extract_bearer(authorization)
    if not tok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing credentials")
    if _is_admin(tok):
        return
    if _token_matches_project(slug, tok):
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "bad credentials for project")


def path_from_header(authorization: str | None) -> str | None:
    """Used only for tests / logging — extracts bearer/basic password if any."""
    return _extract_bearer(authorization)
