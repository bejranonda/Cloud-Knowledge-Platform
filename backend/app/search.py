"""Full-text search over a project vault, backed by SQLite FTS5.

One SQLite DB per project at `<vault>/.ckp/search.db`. The `.ckp/` prefix
is ignored by the watcher (it's under a dotfile parent) and by Obsidian /
LiveSync (same reason), so the index stays local and never replicates.

Public API is unchanged from the previous in-memory implementation:
`reindex(vault_dir)`, `update_file(vault_dir, abs_path)`,
`query(vault_dir, q, limit)`, `snippet(vault_dir, rel, q, around)`.

Scoring: FTS5 `bm25()` with a title-column multiplier so title hits outrank
body hits, matching the old TF+title-boost behaviour.
"""
from __future__ import annotations

import logging
import re
import sqlite3
import threading
from pathlib import Path

log = logging.getLogger(__name__)

_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
    path UNINDEXED,
    title,
    body,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""

# Per-vault write locks. FTS5 writes are serialised per DB; reads can overlap
# in WAL mode.
_locks: dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()

_FTS_SPECIAL = re.compile(r'[^A-Za-z0-9_\- ]+')


def _db_path(vault_dir: Path) -> Path:
    return vault_dir / ".ckp" / "search.db"


def _lock_for(vault_dir: Path) -> threading.Lock:
    key = str(vault_dir)
    with _locks_lock:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _locks[key] = lock
        return lock


def _connect(vault_dir: Path) -> sqlite3.Connection:
    path = _db_path(vault_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5.0, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.executescript(_SCHEMA)
    return conn


def reindex(vault_dir: Path) -> None:
    """Rebuild the index from scratch by walking the vault."""
    lock = _lock_for(vault_dir)
    with lock:
        conn = _connect(vault_dir)
        try:
            conn.execute("BEGIN;")
            conn.execute("DELETE FROM fts;")
            for md in vault_dir.rglob("*.md"):
                rel = md.relative_to(vault_dir)
                if any(part.startswith(".") for part in rel.parts):
                    continue
                try:
                    body = md.read_text(errors="ignore")
                except OSError:
                    continue
                conn.execute(
                    "INSERT INTO fts(path, title, body) VALUES (?, ?, ?);",
                    (rel.as_posix(), md.stem, body),
                )
            conn.execute("COMMIT;")
        finally:
            conn.close()


def update_file(vault_dir: Path, abs_path: Path) -> None:
    """Upsert a single file's entry. Removes the row if the file is gone."""
    try:
        rel = abs_path.relative_to(vault_dir).as_posix()
    except ValueError:
        return
    if any(part.startswith(".") for part in Path(rel).parts):
        return

    body: str | None = None
    title = ""
    if abs_path.is_file() and abs_path.suffix == ".md":
        try:
            body = abs_path.read_text(errors="ignore")
            title = abs_path.stem
        except OSError:
            body = None

    lock = _lock_for(vault_dir)
    with lock:
        conn = _connect(vault_dir)
        try:
            conn.execute("DELETE FROM fts WHERE path = ?;", (rel,))
            if body is not None:
                conn.execute(
                    "INSERT INTO fts(path, title, body) VALUES (?, ?, ?);",
                    (rel, title, body),
                )
        finally:
            conn.close()


def query(vault_dir: Path, q: str, limit: int = 20) -> list[dict]:
    """Return [{'path', 'score'}, …] ranked by bm25 (title-weighted)."""
    match = _to_match(q)
    if not match:
        return []
    conn = _connect(vault_dir)
    try:
        # bm25 with column weights (path=0 ignored, title=5.0, body=1.0).
        # Lower bm25() score is better → negate for a "higher is better"
        # score so the JSON output matches the old contract.
        rows = conn.execute(
            "SELECT path, -bm25(fts, 0.0, 5.0, 1.0) AS score "
            "FROM fts WHERE fts MATCH ? "
            "ORDER BY score DESC LIMIT ?;",
            (match, int(limit)),
        ).fetchall()
    except sqlite3.OperationalError as e:
        log.warning("search query failed: %s (q=%r)", e, q)
        return []
    finally:
        conn.close()
    return [{"path": p, "score": round(s, 2)} for p, s in rows]


def _to_match(q: str) -> str:
    """Turn a user query into an FTS5 MATCH expression.

    FTS5 is picky: bare hyphens, colons, and punctuation blow up the parser.
    Strip them, split on whitespace, and prefix-match each token so typing
    'react' finds 'react-router'. Empty → empty.
    """
    cleaned = _FTS_SPECIAL.sub(" ", q or "").strip()
    if not cleaned:
        return ""
    tokens = [t for t in cleaned.split() if t]
    if not tokens:
        return ""
    return " ".join(f'"{t}"*' for t in tokens)


def snippet(vault_dir: Path, rel: str, q: str, around: int = 60) -> str:
    """First-match context for the query."""
    try:
        text = (vault_dir / rel).read_text(errors="ignore")
    except OSError:
        return ""
    lower = text.lower()
    for term in _FTS_SPECIAL.sub(" ", (q or "").lower()).split():
        if not term:
            continue
        i = lower.find(term)
        if i >= 0:
            a = max(0, i - around)
            b = min(len(text), i + len(term) + around)
            return ("…" if a > 0 else "") + text[a:b].replace("\n", " ") + ("…" if b < len(text) else "")
    return text[:around].replace("\n", " ")
