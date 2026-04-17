# CLAUDE.md — agent working notes

This file is the fast on-ramp for an AI agent (Claude / others) picking up work on this repo. Read it before touching code.

## What this project is
Self-hosted replacement for Obsidian Sync + a Web-App admin layer + Git history + a Hermes Agent pipeline. See `README.md` and `docs/architecture.md`.

## Where things live
- `backend/app/` — FastAPI service. Entry: `backend/app/main.py`.
- `frontend/` — static dashboard, no build step. Served by FastAPI.
- `docs/` — authoritative docs for architecture, client setup, knowledge, issues, guidelines.
- `reference/` — external comparisons.
- `business/` — scope and stakeholders.
- `scripts/` — bootstrap + run.

## How to run locally
```
./scripts/install.sh && ./scripts/start.sh
```
Backend listens on `:8787`. CouchDB on `:5984`. Vaults are in `./vaults/`.

## Conventions
- Python 3.11+, FastAPI, `ruff`, `mypy --strict`.
- One project = one CouchDB DB + one vault dir + one Git repo. Never cross these.
- Keep modules small and single-purpose; split only when a second consumer appears.
- Don't add features speculatively. If requirements unclear, ask.

## Common tasks
- **Add an endpoint**: edit `backend/app/main.py`; keep business logic in the relevant module.
- **Change commit cadence**: `backend/app/versioning.py` (`DEBOUNCE_SECONDS`).
- **Hermes invocation**: `backend/app/hermes.py` — the subprocess call is the one thing you tune per deployment.
- **New project field**: update `backend/app/projects.py` model + the `/projects` view in `frontend/app.js`.

## Gotchas
- Watcher + Git need to serialise writes to avoid racing commits (see `versioning.py` queue).
- Hermes output lands back in the vault → triggers the watcher again → commits. That's intended; don't try to suppress it.
- LiveSync sends many small revisions; debounce matters.
