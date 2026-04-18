# CLAUDE.md — agent working notes

This file is the fast on-ramp for an AI agent (Claude / others) picking up work on this repo. Read it before touching code.

## What this project is
Self-hosted replacement for Obsidian Sync + a Web-App admin layer + Git history + a Hermes Agent pipeline. See `README.md` and `docs/architecture.md`.

## The mental model: DIKW-T
The system is a **DIKW-T pyramid** (Data → Information → Knowledge → Wisdom + Time). One folder per stage in every vault:
- `inbox/` = **Data** (raw capture)
- `notes/` = **Information** (tagged, linked, with frontmatter)
- `knowledge/` = **Knowledge** (Hermes-synthesised evergreen notes)
- `wisdom/` = **Wisdom + Time** (agent-authored "why it changed" notes citing Git history)

Time-series isn't a folder — every stage is versioned in the per-project Git repo. Classifier + `/api/projects/{slug}/dikw` summary live in `backend/app/dikw.py`. Authoritative spec: `docs/dikw-t.md`. Keep this model in mind when adding features; new content usually belongs in one of these four folders.

## Where things live
- `backend/app/` — FastAPI service. Entry: `backend/app/main.py`.
- `frontend/` — static dashboard, no build step. Served by FastAPI.
- `docs/` — authoritative docs for architecture, client setup, knowledge, issues, guidelines.
- `reference/` — external blueprints (Honcho, Obsidian) complete enough to rebuild those platforms from scratch. See `reference/README.md` for the map. Do not edit these to reflect our own changes — edit `docs/` for that.
- `business/` — scope and stakeholders.
- `scripts/` — bootstrap + run.

## How to run locally
```
./scripts/server.sh bootstrap         # bare Ubuntu → installed → started
# or, if OS prereqs are already present:
./scripts/server.sh install && ./scripts/server.sh start
```
Backend listens on `:8787` and serves the frontend at `/` (NOT `/ui/` — it
used to, fixed in v0.3.1). CouchDB on `:5984`. Vaults are in `./vaults/`.

Running tests:
```
./.venv/bin/pytest backend/tests -q
```

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
- The watcher MUST ignore non-mutating inotify events (`opened`, `closed`, `closed_no_write`). Reacting to them caused an infinite feedback loop via `search.update_file` (which reads the file and thus emits another `opened`) that prevented the commit debouncer from ever firing. See `_MUTATING` in `watcher.py`.
- Static assets (`styles.css`, `app.js`, …) are served from `/`, not `/ui/`. `index.html` uses relative paths; mounting at `/ui` would 404. `StaticFiles(html=True)` is mounted LAST so explicit API routes take precedence.
