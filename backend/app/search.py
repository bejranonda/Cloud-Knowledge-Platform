"""Full-text search over a project vault.

Lightweight in-memory inverted index with incremental updates driven by the
watcher. Scoring: term-frequency + title boost. Good enough for vaults up to
~100k notes; swap for a real engine when that stops being true.
"""
from __future__ import annotations

import re
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

_TOKEN = re.compile(r"[a-z0-9][a-z0-9_\-]{1,}")


def _tokenise(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass
class _Index:
    postings: dict[str, dict[str, int]] = field(default_factory=lambda: defaultdict(dict))
    titles: dict[str, list[str]] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


_indexes: dict[str, _Index] = {}
_global_lock = threading.Lock()


def _idx_for(vault_dir: Path) -> _Index:
    with _global_lock:
        return _indexes.setdefault(str(vault_dir), _Index())


def reindex(vault_dir: Path) -> None:
    idx = _Index()
    for md in vault_dir.rglob("*.md"):
        rel = md.relative_to(vault_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue
        try:
            _insert(idx, vault_dir, md)
        except OSError:
            continue
    with _global_lock:
        _indexes[str(vault_dir)] = idx


def update_file(vault_dir: Path, abs_path: Path) -> None:
    idx = _idx_for(vault_dir)
    try:
        rel = abs_path.relative_to(vault_dir).as_posix()
    except ValueError:
        return
    with idx.lock:
        _remove(idx, rel)
        if abs_path.is_file():
            _insert(idx, vault_dir, abs_path)


def _remove(idx: _Index, rel: str) -> None:
    for term in list(idx.postings):
        if rel in idx.postings[term]:
            del idx.postings[term][rel]
            if not idx.postings[term]:
                del idx.postings[term]
    idx.titles.pop(rel, None)


def _insert(idx: _Index, vault_dir: Path, abs_path: Path) -> None:
    rel = abs_path.relative_to(vault_dir).as_posix()
    text = abs_path.read_text(errors="ignore")
    tokens = _tokenise(text)
    counts = Counter(tokens)
    for term, n in counts.items():
        idx.postings[term][rel] = n
    idx.titles[rel] = _tokenise(abs_path.stem)


def query(vault_dir: Path, q: str, limit: int = 20) -> list[dict]:
    idx = _idx_for(vault_dir)
    terms = _tokenise(q)
    if not terms:
        return []
    with idx.lock:
        scores: dict[str, float] = defaultdict(float)
        for term in terms:
            postings = idx.postings.get(term, {})
            for doc, tf in postings.items():
                scores[doc] += tf
                if term in idx.titles.get(doc, []):
                    scores[doc] += 5.0
        if not scores:
            return []
        top = sorted(scores.items(), key=lambda x: -x[1])[:limit]
        return [{"path": p, "score": round(s, 2)} for p, s in top]


def snippet(vault_dir: Path, rel: str, q: str, around: int = 60) -> str:
    """First match context for the query."""
    try:
        text = (vault_dir / rel).read_text(errors="ignore")
    except OSError:
        return ""
    lower = text.lower()
    for term in _tokenise(q):
        i = lower.find(term)
        if i >= 0:
            a = max(0, i - around)
            b = min(len(text), i + len(term) + around)
            return ("…" if a > 0 else "") + text[a:b].replace("\n", " ") + ("…" if b < len(text) else "")
    return text[:around].replace("\n", " ")
