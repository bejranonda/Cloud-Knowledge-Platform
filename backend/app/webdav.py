"""WebDAV handler for Obsidian *Remotely Save* plugin.

Serves one CKP project vault per URL prefix: ``/webdav/{slug}/...``.
Implements RFC 4918 WebDAV at the level required by Remotely Save:
OPTIONS, GET, HEAD, PUT, DELETE, MKCOL, PROPFIND, PROPPATCH, MOVE, COPY,
LOCK, UNLOCK.

Mount point in main.py::

    from .webdav import router as webdav_router
    app.include_router(webdav_router, prefix="/webdav")
"""
from __future__ import annotations

import hashlib
import secrets
import shutil
import urllib.parse
from email.utils import formatdate
from pathlib import Path
from textwrap import dedent
from typing import Any
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from . import auth, events, projects, search, versioning

router = APIRouter()

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

_DAV_NS = "DAV:"


def _check_auth(slug: str, authorization: str | None) -> None:
    """Delegate to auth.require_for_project: accepts admin token OR a
    per-project token matching `slug`. Auth is disabled if no admin token
    and no project credentials exist."""
    auth.require_for_project(slug, authorization)


# ---------------------------------------------------------------------------
# Path safety helpers
# ---------------------------------------------------------------------------

def _safe_path(vault_dir: Path, rel: str) -> Path:
    """Resolve *rel* inside *vault_dir* and raise 403 on escape or .git access."""
    # strip leading slashes so Path doesn't treat it as absolute
    rel_clean = rel.lstrip("/")
    target = (vault_dir / rel_clean).resolve()
    try:
        target.relative_to(vault_dir.resolve())
    except ValueError:
        raise HTTPException(403, "path escape")
    if ".git" in target.parts:
        raise HTTPException(403, "access to .git denied")
    return target


def _rel(vault_dir: Path, abs_path: Path) -> str:
    """Relative POSIX path from vault root."""
    return abs_path.relative_to(vault_dir).as_posix()


# ---------------------------------------------------------------------------
# Hook helpers (non-blocking — all delegates are fire-and-forget threads)
# ---------------------------------------------------------------------------

def _after_write(proj: projects.Project, abs_path: Path, method: str) -> None:
    rel = _rel(proj.vault_dir, abs_path)
    versioning.schedule_commit(proj.vault_dir, reason=f"webdav: {method} {rel}")
    search.update_file(proj.vault_dir, abs_path)
    events.emit("fs", {"project": proj.slug, "path": rel, "op": method.lower()})


def _after_dir_write(proj: projects.Project, abs_path: Path, method: str) -> None:
    rel = _rel(proj.vault_dir, abs_path)
    versioning.schedule_commit(proj.vault_dir, reason=f"webdav: {method} {rel}")
    events.emit("fs", {"project": proj.slug, "path": rel, "op": method.lower()})


# ---------------------------------------------------------------------------
# PROPFIND XML builder
# ---------------------------------------------------------------------------

def _etag(path: Path) -> str:
    st = path.stat()
    raw = f"{st.st_mtime_ns}-{st.st_size}"
    return hashlib.md5(raw.encode()).hexdigest()  # noqa: S324


def _prop_xml(href: str, path: Path) -> ET.Element:
    """Build a single <response> element for *path*."""
    response = ET.Element(f"{{{_DAV_NS}}}response")
    ET.SubElement(response, f"{{{_DAV_NS}}}href").text = href

    propstat = ET.SubElement(response, f"{{{_DAV_NS}}}propstat")
    prop = ET.SubElement(propstat, f"{{{_DAV_NS}}}prop")

    # displayname
    ET.SubElement(prop, f"{{{_DAV_NS}}}displayname").text = path.name or "/"

    is_dir = path.is_dir()
    st = path.stat()

    # resourcetype
    rt = ET.SubElement(prop, f"{{{_DAV_NS}}}resourcetype")
    if is_dir:
        ET.SubElement(rt, f"{{{_DAV_NS}}}collection")

    # contentlength (0 for dirs)
    ET.SubElement(prop, f"{{{_DAV_NS}}}getcontentlength").text = (
        "0" if is_dir else str(st.st_size)
    )

    # getlastmodified RFC1123
    ET.SubElement(prop, f"{{{_DAV_NS}}}getlastmodified").text = formatdate(
        st.st_mtime, usegmt=True
    )

    # getetag
    ET.SubElement(prop, f"{{{_DAV_NS}}}getetag").text = f'"{_etag(path)}"'

    ET.SubElement(propstat, f"{{{_DAV_NS}}}status").text = "HTTP/1.1 200 OK"
    return response


def _multistatus(responses: list[ET.Element]) -> str:
    root = ET.Element(
        f"{{{_DAV_NS}}}multistatus",
        {"xmlns:D": _DAV_NS},
    )
    for r in responses:
        root.append(r)
    return '<?xml version="1.0" encoding="utf-8"?>' + ET.tostring(
        root, encoding="unicode"
    )


def _propfind_response(
    vault_dir: Path, abs_path: Path, href_base: str, depth: str
) -> Response:
    """Build 207 multistatus for PROPFIND."""
    if not abs_path.exists():
        raise HTTPException(404, "not found")

    # Normalise href_base: ensure trailing slash for collections
    href_self = href_base.rstrip("/")
    if abs_path.is_dir():
        href_self += "/"

    responses: list[ET.Element] = [_prop_xml(href_self, abs_path)]

    if abs_path.is_dir() and depth != "0":
        children = list(abs_path.iterdir())
        if depth == "1":
            for child in children:
                child_href = href_self.rstrip("/") + "/" + urllib.parse.quote(child.name)
                if child.is_dir():
                    child_href += "/"
                responses.append(_prop_xml(child_href, child))
        else:  # infinity
            for child in abs_path.rglob("*"):
                try:
                    rel_parts = child.relative_to(abs_path).parts
                except ValueError:
                    continue
                child_href = href_self.rstrip("/") + "/" + "/".join(
                    urllib.parse.quote(p) for p in rel_parts
                )
                if child.is_dir():
                    child_href += "/"
                responses.append(_prop_xml(child_href, child))

    xml = _multistatus(responses)
    return Response(
        content=xml.encode("utf-8"),
        status_code=207,
        media_type='application/xml; charset="utf-8"',
    )


# ---------------------------------------------------------------------------
# Destination header parser (for MOVE/COPY)
# ---------------------------------------------------------------------------

def _parse_destination(
    destination_header: str, slug: str, prefix: str
) -> str:
    """Extract vault-relative path from a Destination header value.

    The header may be an absolute URL or an absolute path.  We strip the
    scheme+host and the WebDAV prefix to get the relative path inside the
    vault.
    """
    parsed = urllib.parse.urlparse(destination_header)
    path = parsed.path if parsed.scheme else destination_header
    # path should now start with /webdav/{slug}/...
    expected_prefix = f"{prefix}/{slug}/"
    if not path.startswith(expected_prefix):
        raise HTTPException(400, "Destination outside this vault")
    return urllib.parse.unquote(path[len(expected_prefix):])


# ---------------------------------------------------------------------------
# LOCK / UNLOCK helpers
# ---------------------------------------------------------------------------

def _lock_response(href: str) -> Response:
    """Return a minimal advisory lock response."""
    token = f"urn:uuid:{secrets.token_hex(16)}"
    body = dedent(f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <D:prop xmlns:D="DAV:">
          <D:lockdiscovery>
            <D:activelock>
              <D:locktype><D:write/></D:locktype>
              <D:lockscope><D:exclusive/></D:lockscope>
              <D:depth>0</D:depth>
              <D:timeout>Second-3600</D:timeout>
              <D:locktoken><D:href>{token}</D:href></D:locktoken>
              <D:lockroot><D:href>{href}</D:href></D:lockroot>
            </D:activelock>
          </D:lockdiscovery>
        </D:prop>
    """)
    return Response(
        content=body.encode("utf-8"),
        status_code=200,
        headers={"Lock-Token": f"<{token}>"},
        media_type='application/xml; charset="utf-8"',
    )


# ---------------------------------------------------------------------------
# Main dispatcher — catches all methods for /{slug}/{path:path}
# ---------------------------------------------------------------------------

_ALLOW = "OPTIONS, GET, HEAD, PUT, DELETE, PROPFIND, PROPPATCH, MKCOL, COPY, MOVE, LOCK, UNLOCK"
_WEBDAV_PREFIX = "/webdav"  # must match the prefix used in main.py include_router


@router.api_route(
    "/{slug}/{path:path}",
    methods=["OPTIONS", "GET", "HEAD", "PUT", "DELETE",
             "PROPFIND", "PROPPATCH", "MKCOL", "COPY", "MOVE",
             "LOCK", "UNLOCK"],
)
@router.api_route(
    "/{slug}",
    methods=["OPTIONS", "GET", "HEAD", "PUT", "DELETE",
             "PROPFIND", "PROPPATCH", "MKCOL", "COPY", "MOVE",
             "LOCK", "UNLOCK"],
)
async def webdav_handler(
    slug: str,
    request: Request,
    path: str = "",
    authorization: str | None = Header(default=None),
) -> Any:
    method = request.method.upper()

    # OPTIONS is the pre-auth probe; skip auth so clients can discover DAV level.
    if method == "OPTIONS":
        return Response(
            status_code=200,
            headers={
                "DAV": "1,2",
                "Allow": _ALLOW,
                "Content-Length": "0",
            },
        )

    # Authenticate (per-project or admin)
    _check_auth(slug, authorization)

    # Resolve project
    proj = projects.get(slug)
    if proj is None:
        raise HTTPException(404, f"project '{slug}' not found")

    vault_dir = proj.vault_dir
    rel = path.lstrip("/")
    abs_path = _safe_path(vault_dir, rel) if rel else vault_dir.resolve()

    # Build the href for this resource (used in PROPFIND / LOCK)
    encoded_rel = "/".join(urllib.parse.quote(p) for p in Path(rel).parts) if rel else ""
    href = f"{_WEBDAV_PREFIX}/{slug}/{encoded_rel}"

    # -----------------------------------------------------------------------
    # GET / HEAD
    # -----------------------------------------------------------------------
    if method in ("GET", "HEAD"):
        if not abs_path.exists():
            raise HTTPException(404, "not found")
        if abs_path.is_dir():
            raise HTTPException(405, "cannot GET a directory")

        st = abs_path.stat()
        headers: dict[str, str] = {
            "Content-Length": str(st.st_size),
            "Last-Modified": formatdate(st.st_mtime, usegmt=True),
            "ETag": f'"{_etag(abs_path)}"',
            "Content-Type": "application/octet-stream",
        }
        if method == "HEAD":
            return Response(status_code=200, headers=headers)

        async def _iter_file():
            with abs_path.open("rb") as fh:
                while chunk := fh.read(65536):
                    yield chunk

        return StreamingResponse(_iter_file(), status_code=200, headers=headers)

    # -----------------------------------------------------------------------
    # PUT
    # -----------------------------------------------------------------------
    if method == "PUT":
        if not rel:
            raise HTTPException(405, "cannot PUT to vault root")
        created = not abs_path.exists()
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        body = await request.body()
        abs_path.write_bytes(body)
        _after_write(proj, abs_path, "PUT")
        return Response(status_code=201 if created else 204)

    # -----------------------------------------------------------------------
    # DELETE
    # -----------------------------------------------------------------------
    if method == "DELETE":
        if not abs_path.exists():
            raise HTTPException(404, "not found")
        if abs_path.is_dir():
            shutil.rmtree(abs_path)
        else:
            abs_path.unlink()
        _after_dir_write(proj, vault_dir, "DELETE")
        return Response(status_code=204)

    # -----------------------------------------------------------------------
    # MKCOL
    # -----------------------------------------------------------------------
    if method == "MKCOL":
        body = await request.body()
        if body:
            raise HTTPException(415, "MKCOL body not supported")
        if abs_path.exists():
            raise HTTPException(405, "already exists")
        abs_path.mkdir(parents=True, exist_ok=False)
        _after_dir_write(proj, abs_path, "MKCOL")
        return Response(status_code=201)

    # -----------------------------------------------------------------------
    # PROPFIND
    # -----------------------------------------------------------------------
    if method == "PROPFIND":
        depth = request.headers.get("Depth", "1")
        if depth not in ("0", "1", "infinity"):
            depth = "1"
        return _propfind_response(vault_dir, abs_path, href, depth)

    # -----------------------------------------------------------------------
    # PROPPATCH — accept and no-op; return 207 success
    # -----------------------------------------------------------------------
    if method == "PROPPATCH":
        if not abs_path.exists():
            raise HTTPException(404, "not found")
        encoded_rel2 = "/".join(urllib.parse.quote(p) for p in Path(rel).parts) if rel else ""
        href2 = f"{_WEBDAV_PREFIX}/{slug}/{encoded_rel2}"
        xml = (
            '<?xml version="1.0" encoding="utf-8"?>'
            f'<D:multistatus xmlns:D="DAV:">'
            f'<D:response><D:href>{href2}</D:href>'
            f'<D:propstat><D:prop/>'
            f'<D:status>HTTP/1.1 200 OK</D:status></D:propstat>'
            f'</D:response></D:multistatus>'
        )
        return Response(
            content=xml.encode("utf-8"),
            status_code=207,
            media_type='application/xml; charset="utf-8"',
        )

    # -----------------------------------------------------------------------
    # MOVE / COPY
    # -----------------------------------------------------------------------
    if method in ("MOVE", "COPY"):
        dest_header = request.headers.get("Destination")
        if not dest_header:
            raise HTTPException(400, "missing Destination header")
        dest_rel = _parse_destination(dest_header, slug, _WEBDAV_PREFIX)
        dest_abs = _safe_path(vault_dir, dest_rel)
        overwrite = request.headers.get("Overwrite", "T").upper() != "F"

        if dest_abs.exists():
            if not overwrite:
                raise HTTPException(412, "destination exists and Overwrite is F")
            if dest_abs.is_dir():
                shutil.rmtree(dest_abs)
            else:
                dest_abs.unlink()

        dest_abs.parent.mkdir(parents=True, exist_ok=True)
        created = not dest_abs.exists()

        if method == "MOVE":
            shutil.move(str(abs_path), str(dest_abs))
        else:
            if abs_path.is_dir():
                shutil.copytree(str(abs_path), str(dest_abs))
            else:
                shutil.copy2(str(abs_path), str(dest_abs))

        _after_dir_write(proj, vault_dir, method)
        return Response(status_code=201 if created else 204)

    # -----------------------------------------------------------------------
    # LOCK — advisory; return a fake token so clients don't stall
    # -----------------------------------------------------------------------
    if method == "LOCK":
        # Create the file if it doesn't exist (lock on new resource)
        if not abs_path.exists() and rel:
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_bytes(b"")
        return _lock_response(href)

    # -----------------------------------------------------------------------
    # UNLOCK — always succeed
    # -----------------------------------------------------------------------
    if method == "UNLOCK":
        return Response(status_code=204)

    raise HTTPException(405, f"method {method} not supported")
