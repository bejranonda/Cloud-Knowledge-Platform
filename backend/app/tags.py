"""Tag index: inline #tags + frontmatter tags, aggregated per project."""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from . import frontmatter

_INLINE_TAG = re.compile(r"(?:^|\s)#([a-zA-Z][\w\-/]*)")


def tags_in(text: str) -> set[str]:
    fm, body = frontmatter.split(text)
    out = set(frontmatter.tags_from(fm))
    for m in _INLINE_TAG.finditer(body):
        out.add(m.group(1))
    return out


def build_index(vault_dir: Path) -> dict[str, list[str]]:
    """Map tag -> [note paths]."""
    idx: dict[str, list[str]] = defaultdict(list)
    for md in vault_dir.rglob("*.md"):
        rel = md.relative_to(vault_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue
        try:
            text = md.read_text(errors="ignore")
        except OSError:
            continue
        for t in tags_in(text):
            idx[t].append(rel.as_posix())
    return dict(sorted(idx.items()))
