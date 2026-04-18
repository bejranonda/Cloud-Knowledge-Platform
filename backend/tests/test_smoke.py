"""End-to-end smoke tests for Cloud Knowledge Platform.

Exercises the full request → watcher → git → search → history pipeline
using FastAPI's TestClient (no real network, no Docker required).

The session-scoped `client` fixture is provided by conftest.py, which
sets the four env vars and starts the app lifespan before yielding.
"""
from __future__ import annotations

import base64
import time
from io import BytesIO

import pytest

# ---------------------------------------------------------------------------
# Auth header shorthand
# ---------------------------------------------------------------------------
H = {"Authorization": "Bearer test-admin-token"}


# ---------------------------------------------------------------------------
# Polling helper
# ---------------------------------------------------------------------------

def wait_until(fn, timeout: float = 5.0, interval: float = 0.1, msg: str = "condition never became true"):
    """Repeatedly call fn() until it returns a truthy value or timeout expires.

    Raises AssertionError with *msg* on timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = fn()
        if result:
            return result
        time.sleep(interval)
    raise AssertionError(f"wait_until timed out after {timeout}s: {msg}")


# ---------------------------------------------------------------------------
# 1. Health check
# ---------------------------------------------------------------------------

def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["auth_required"] is True


# ---------------------------------------------------------------------------
# 2. Project CRUD + auth guard
# ---------------------------------------------------------------------------

def test_project_crud_requires_auth(client):
    # No token → 401
    r = client.post("/api/projects", json={"slug": "proj-a", "display_name": "Project A"})
    assert r.status_code == 401

    # With admin token → 200
    r = client.post(
        "/api/projects",
        json={"slug": "proj-a", "display_name": "Project A"},
        headers=H,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "proj-a"

    # List projects contains the new one
    r = client.get("/api/projects")
    assert r.status_code == 200
    slugs = [p["slug"] for p in r.json()]
    assert "proj-a" in slugs


# ---------------------------------------------------------------------------
# 3. Write / read note and wait for git commit
# ---------------------------------------------------------------------------

def test_write_read_note_and_commit(client):
    content = "# Hello\n\nWorld"
    r = client.put(
        "/api/projects/proj-a/note",
        json={"path": "notes/hello.md", "content": content},
        headers=H,
    )
    assert r.status_code == 200

    # Read back immediately
    r = client.get("/api/projects/proj-a/note", params={"path": "notes/hello.md"})
    assert r.status_code == 200
    assert r.text == content

    # Poll until at least one commit mentioning hello.md lands
    def _has_commit():
        r = client.get("/api/projects/proj-a/history")
        if r.status_code != 200:
            return False
        return any("hello.md" in c["msg"] for c in r.json())

    wait_until(_has_commit, timeout=5.0, msg="expected a commit mentioning hello.md")


# ---------------------------------------------------------------------------
# 4. Search and tags
# ---------------------------------------------------------------------------

def test_search_and_tags(client):
    note_path = "notes/zebra-note.md"
    content = "# Hello zebra\n\n#alpha #beta\n\nSome unique word: zebra"
    r = client.put(
        "/api/projects/proj-a/note",
        json={"path": note_path, "content": content},
        headers=H,
    )
    assert r.status_code == 200

    # Poll search until the note appears
    def _search_hit():
        r = client.get("/api/projects/proj-a/search", params={"q": "zebra"})
        if r.status_code != 200:
            return False
        hits = r.json()
        return any(h["path"].endswith("zebra-note.md") for h in hits)

    wait_until(_search_hit, timeout=5.0, msg="search for 'zebra' did not return zebra-note.md")

    # Tags index should contain alpha and beta
    r = client.get("/api/projects/proj-a/tags")
    assert r.status_code == 200
    tag_index = r.json()
    assert "alpha" in tag_index
    assert "beta" in tag_index


# ---------------------------------------------------------------------------
# 5. Backlinks
# ---------------------------------------------------------------------------

def test_backlinks(client):
    r = client.put(
        "/api/projects/proj-a/note",
        json={"path": "notes/a.md", "content": "links to [[b]]"},
        headers=H,
    )
    assert r.status_code == 200

    r = client.put(
        "/api/projects/proj-a/note",
        json={"path": "notes/b.md", "content": "# B note"},
        headers=H,
    )
    assert r.status_code == 200

    def _has_backlink():
        r = client.get(
            "/api/projects/proj-a/backlinks",
            params={"path": "notes/b.md"},
        )
        if r.status_code != 200:
            return False
        return any("a.md" in item.get("path", "") for item in r.json())

    wait_until(_has_backlink, timeout=5.0, msg="backlinks for notes/b.md never showed notes/a.md")


# ---------------------------------------------------------------------------
# 6. File history and restore
# ---------------------------------------------------------------------------

def test_file_history_and_restore(client):
    note_path = "notes/versioned.md"
    content_v1 = "# Version one"
    content_v2 = "# Version two"

    # First write
    r = client.put(
        "/api/projects/proj-a/note",
        json={"path": note_path, "content": content_v1},
        headers=H,
    )
    assert r.status_code == 200

    # Poll until commit for v1 exists
    def _v1_committed():
        r = client.get("/api/projects/proj-a/history/file", params={"path": note_path})
        return r.status_code == 200 and len(r.json()) >= 1

    wait_until(_v1_committed, timeout=5.0, msg="v1 commit did not appear")

    # Second write
    r = client.put(
        "/api/projects/proj-a/note",
        json={"path": note_path, "content": content_v2},
        headers=H,
    )
    assert r.status_code == 200

    # Poll until at least 2 commits for this file
    def _two_commits():
        r = client.get("/api/projects/proj-a/history/file", params={"path": note_path})
        return r.status_code == 200 and len(r.json()) >= 2

    wait_until(_two_commits, timeout=5.0, msg="did not get 2 commits for versioned.md")

    entries = client.get("/api/projects/proj-a/history/file", params={"path": note_path}).json()
    assert len(entries) >= 2

    # Oldest commit is last in the list
    oldest_hash = entries[-1]["hash"]

    # Restore to oldest version
    r = client.post(
        "/api/projects/proj-a/history/restore",
        params={"commit": oldest_hash, "path": note_path},
        headers=H,
    )
    assert r.status_code == 200

    # Read back — should be v1
    r = client.get("/api/projects/proj-a/note", params={"path": note_path})
    assert r.status_code == 200
    assert content_v1 in r.text


# ---------------------------------------------------------------------------
# 7. Per-project token scoped access
# ---------------------------------------------------------------------------

def test_project_token_scoped_access(client):
    # Issue a project-scoped token for proj-a
    r = client.post("/api/projects/proj-a/credentials", headers=H)
    assert r.status_code == 200
    proj_a_token = r.json()["token"]
    proj_a_h = {"Authorization": f"Bearer {proj_a_token}"}

    # proj-a token can write to proj-a
    r = client.put(
        "/api/projects/proj-a/note",
        json={"path": "notes/scoped.md", "content": "scoped write"},
        headers=proj_a_h,
    )
    assert r.status_code == 200

    # Create proj-b
    r = client.post(
        "/api/projects",
        json={"slug": "proj-b", "display_name": "Project B"},
        headers=H,
    )
    assert r.status_code == 200

    # proj-a token cannot write to proj-b → 403
    r = client.put(
        "/api/projects/proj-b/note",
        json={"path": "notes/scoped.md", "content": "should be denied"},
        headers=proj_a_h,
    )
    assert r.status_code == 403

    # Admin can write to proj-b
    r = client.put(
        "/api/projects/proj-b/note",
        json={"path": "notes/admin-write.md", "content": "admin write"},
        headers=H,
    )
    assert r.status_code == 200

    # Admin can also write to proj-a
    r = client.put(
        "/api/projects/proj-a/note",
        json={"path": "notes/admin-write-a.md", "content": "admin write a"},
        headers=H,
    )
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# 8. WebDAV PUT + PROPFIND
# ---------------------------------------------------------------------------

def test_webdav_put_and_propfind(client):
    # Build Basic auth header: user:test-admin-token
    creds = base64.b64encode(b"user:test-admin-token").decode()
    dav_h = {"Authorization": f"Basic {creds}"}

    # PUT a file via WebDAV
    r = client.put(
        "/webdav/proj-a/notes/webdav-note.md",
        content=b"# from webdav",
        headers=dav_h,
    )
    assert r.status_code in (201, 204), f"WebDAV PUT returned {r.status_code}"

    # Poll /api/projects/proj-a/tree until the file appears
    def _in_tree():
        r = client.get("/api/projects/proj-a/tree")
        if r.status_code != 200:
            return False
        return any(f["path"] == "notes/webdav-note.md" for f in r.json())

    wait_until(_in_tree, timeout=5.0, msg="webdav-note.md did not appear in project tree")

    # PROPFIND the directory — expect 207
    r = client.request(
        "PROPFIND",
        "/webdav/proj-a/notes/",
        headers={**dav_h, "Depth": "1"},
    )
    assert r.status_code == 207
    assert "webdav-note.md" in r.text


# ---------------------------------------------------------------------------
# 9. Attachment upload and serve
# ---------------------------------------------------------------------------

def test_attachment_upload_and_serve(client):
    # Minimal PNG-like bytes (8-byte PNG magic header)
    png_bytes = b"\x89PNG\r\n\x1a\n"

    r = client.post(
        "/api/projects/proj-a/attachments",
        files={"file": ("test-image.png", BytesIO(png_bytes), "image/png")},
        headers=H,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["path"].startswith("attachments/")

    # Extract the filename from the returned path
    att_name = body["path"][len("attachments/"):]

    # GET the attachment back
    r = client.get(f"/api/projects/proj-a/attachments/{att_name}")
    assert r.status_code == 200
    assert r.content == png_bytes
    ct = r.headers.get("content-type", "")
    assert "image" in ct or "octet" in ct


# ---------------------------------------------------------------------------
# 10. Hermes retrigger
# ---------------------------------------------------------------------------

def test_hermes_retrigger(client):
    # PUT a note in inbox/ — watcher or the schedule_commit will pick this up
    r = client.put(
        "/api/projects/proj-a/note",
        json={"path": "inbox/info-1.md", "content": "# Info file\n\nData here."},
        headers=H,
    )
    assert r.status_code == 200

    # Poll until at least one Hermes job for proj-a reaches a terminal state
    def _job_done():
        r = client.get("/api/hermes/jobs")
        if r.status_code != 200:
            return False
        jobs = r.json()
        return any(
            j["project"] == "proj-a" and j["status"] in ("ok", "failed")
            for j in jobs
        )

    wait_until(
        _job_done,
        timeout=15.0,  # give hermes workers a bit more time
        interval=0.2,
        msg="no completed Hermes job found for proj-a",
    )

    # Retrigger via the API
    r = client.post(
        "/api/projects/proj-a/hermes/retrigger",
        params={"path": "inbox/info-1.md"},
        headers=H,
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True


# ---------------------------------------------------------------------------
# 11. DIKW-T stage summary
# ---------------------------------------------------------------------------

def test_dikw_summary(client):
    # Seed one note of each kind
    writes = [
        ("inbox/raw.md", "just a dump"),                              # Data
        ("notes/structured.md", "---\ntags: [x]\n---\n# Info"),       # Information
        ("knowledge/evergreen.md", "# Evergreen"),                    # Knowledge
        ("wisdom/why.md", "# Why it changed"),                        # Wisdom
    ]
    for path, content in writes:
        r = client.put(
            "/api/projects/proj-a/note",
            json={"path": path, "content": content},
            headers=H,
        )
        assert r.status_code == 200, f"put {path} failed: {r.text}"

    r = client.get("/api/projects/proj-a/dikw")
    assert r.status_code == 200
    body = r.json()
    assert body["project"] == "proj-a"
    counts = body["counts"]
    assert counts["data"] >= 1
    assert counts["information"] >= 1
    assert counts["knowledge"] >= 1
    assert counts["wisdom"] >= 1
    assert body["total"] >= 4
    assert body["commits"] >= 1


# ---------------------------------------------------------------------------
# 12. Tree includes DIKW-T stage per markdown file
# ---------------------------------------------------------------------------

def test_tree_reports_dikw_stage(client):
    r = client.get("/api/projects/proj-a/tree")
    assert r.status_code == 200
    tree = r.json()
    by_path = {f["path"]: f for f in tree}

    # At least one file in each stage from the seed above
    assert by_path["inbox/raw.md"]["stage"] == "data"
    assert by_path["notes/structured.md"]["stage"] == "information"
    assert by_path["knowledge/evergreen.md"]["stage"] == "knowledge"
    assert by_path["wisdom/why.md"]["stage"] == "wisdom"
