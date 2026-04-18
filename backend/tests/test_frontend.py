"""Frontend smoke tests.

Zero-build discipline: we verify the static bundle is served correctly and
the JS parses, without introducing a browser runtime. Covers:

1. `/` returns index.html with expected scaffolding (views, DIKW section,
   promote button).
2. `app.js` is served with the right MIME, contains the DIKW and promote
   code paths, and passes a Node syntax check.
3. `styles.css` is served and includes the DIKW stage styles.

Browser-level behaviour is out of scope for these tests — add Playwright
later if the frontend grows beyond "declarative".
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


def test_index_html_served(client):
    r = client.get("/")
    assert r.status_code == 200, r.text
    html = r.text
    # View scaffolding still present
    for ident in ('id="view-editor"', 'id="view-dikw"', 'id="view-hermes"'):
        assert ident in html, f"missing: {ident}"
    # DIKW tab button
    assert 'data-view="dikw"' in html
    # Promote button + wisdom button exist
    assert 'id="promote-note"' in html
    assert 'id="wisdom-synth-btn"' in html


def test_app_js_served_and_parses(client):
    r = client.get("/app.js")
    assert r.status_code == 200, r.text
    js = r.text
    ct = r.headers.get("content-type", "")
    assert "javascript" in ct or "ecmascript" in ct, f"bad content-type: {ct}"

    # Smoke markers for critical code paths
    for token in ("loadDikw", "promote-note", "/dikw", "/wisdom/synthesise"):
        assert token in js, f"app.js missing: {token}"

    # Node syntax check — fast, catches malformed JS immediately
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed; skipping syntax check")
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False) as f:
        f.write(js)
        tmp = Path(f.name)
    try:
        result = subprocess.run(
            [node, "--check", str(tmp)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"app.js syntax error:\n{result.stderr}"
    finally:
        tmp.unlink(missing_ok=True)


def test_styles_css_served(client):
    r = client.get("/styles.css")
    assert r.status_code == 200
    css = r.text
    for cls in (".stage-data", ".stage-information", ".stage-knowledge", ".stage-wisdom", ".dikw-cards"):
        assert cls in css, f"styles.css missing: {cls}"
