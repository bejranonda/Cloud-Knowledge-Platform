"""DIKW-T stage classifier.

Maps each markdown file in a vault to one of four stages:

    data          - raw capture (inbox/, or files with no structure)
    information   - organised notes (notes/, or files with frontmatter/links)
    knowledge     - synthesised output (knowledge/)
    wisdom        - time-series reasoning (wisdom/)

The classifier is a pure function over the on-disk vault. No state. Callers
derive aggregate counts for the /dikw endpoint or to drive UI widgets.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Literal

from . import frontmatter

Stage = Literal["data", "information", "knowledge", "wisdom"]

_WIKILINK_RE = re.compile(r"\[\[[^\]]+\]\]")
_HASHTAG_RE = re.compile(r"(?:^|\s)#[A-Za-z][\w/-]*")


def classify(rel_path: Path, body: str | None = None) -> Stage:
    """Classify *rel_path* (relative to vault root). *body* is optional file text;
    when omitted, classification is purely folder-based.
    """
    parts = rel_path.parts
    if not parts:
        return "data"
    top = parts[0]
    if top == "knowledge":
        return "knowledge"
    if top == "wisdom":
        return "wisdom"
    if top == "inbox":
        return "data"
    if top == "notes":
        # Heuristic: a file inside notes/ that still has no structure is Data.
        if body is not None and not _has_structure(body):
            return "data"
        return "information"
    # Anywhere else: promote to Information iff it has structure.
    if body is not None and _has_structure(body):
        return "information"
    return "data"


def _has_structure(body: str) -> bool:
    fm, rest = frontmatter.split(body)
    if fm:
        return True
    if _WIKILINK_RE.search(rest):
        return True
    if _HASHTAG_RE.search(rest):
        return True
    return False


def summarise(vault_dir: Path) -> dict:
    """Walk the vault and return counts per stage plus Git time-series stats."""
    counts: dict[Stage, int] = {"data": 0, "information": 0, "knowledge": 0, "wisdom": 0}
    total = 0
    for p in vault_dir.rglob("*.md"):
        rel = p.relative_to(vault_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue
        try:
            body = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            body = None
        stage = classify(rel, body)
        counts[stage] += 1
        total += 1
    commits, first_ts, last_ts = _git_stats(vault_dir)
    return {
        "counts": counts,
        "total": total,
        "commits": commits,
        "first_commit_ts": first_ts,
        "last_commit_ts": last_ts,
    }


def _git_stats(vault_dir: Path) -> tuple[int, int | None, int | None]:
    if not (vault_dir / ".git").exists():
        return 0, None, None
    try:
        out = subprocess.run(
            ["git", "log", "--format=%ct"],
            cwd=vault_dir,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except subprocess.CalledProcessError:
        return 0, None, None
    ts = [int(x) for x in out.split() if x.strip().isdigit()]
    if not ts:
        return 0, None, None
    return len(ts), min(ts), max(ts)
