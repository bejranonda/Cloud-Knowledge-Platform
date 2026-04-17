"""/api/projects/{slug}/credentials — issue and revoke per-project tokens."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .. import auth
from ..util import proj_or_404

router = APIRouter(prefix="/api/projects", tags=["credentials"])


@router.get("/{slug}/credentials", dependencies=[Depends(auth.require_admin)])
def list_credentials(slug: str) -> dict:
    proj_or_404(slug)
    return {"tokens": auth.list_tokens(slug)}


@router.post("/{slug}/credentials", dependencies=[Depends(auth.require_admin)])
def create_credential(slug: str) -> dict:
    """Return the new token in full — only time it's shown."""
    proj_or_404(slug)
    tok = auth.issue_token(slug)
    return {"token": tok}


@router.delete("/{slug}/credentials", dependencies=[Depends(auth.require_admin)])
def delete_credential(slug: str, prefix: str) -> dict:
    """Revoke the token whose first 6 chars match `prefix`."""
    proj_or_404(slug)
    ok = auth.revoke_token(slug, prefix)
    return {"ok": ok}
