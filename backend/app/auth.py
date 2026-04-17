"""Minimal admin auth: shared bearer token via env CKP_ADMIN_TOKEN.

If the env var is unset, auth is disabled (dev mode). Production deployments
MUST set it; the dashboard stores it in localStorage and sends it as a
`Bearer` token on every mutating request.
"""
from __future__ import annotations

import os
import secrets

from fastapi import Header, HTTPException, status

_TOKEN = os.getenv("CKP_ADMIN_TOKEN", "").strip()


def enabled() -> bool:
    return bool(_TOKEN)


def require(authorization: str | None = Header(default=None)) -> None:
    if not _TOKEN:
        return  # dev mode
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    given = authorization.split(" ", 1)[1].strip()
    if not secrets.compare_digest(given, _TOKEN):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "bad token")
