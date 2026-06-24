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
./scripts/server.sh bootstrap         # bare Ubuntu → installed → started (dev/lab)
# or, if OS prereqs are already present:
./scripts/server.sh install && ./scripts/server.sh start
```

## How to deploy to a new server
```
sudo DOMAIN=ckp.example.com ./scripts/deploy-new-server.sh   # production wrapper
```
Single-command bootstrap of a fresh Ubuntu/Debian box: installs prereqs,
clones the repo to `/opt/ckp`, generates `.env` with random secrets,
optionally patches `deploy/caddy/Caddyfile` with `DOMAIN`, then runs
`server.sh deploy`. Install-only — for ongoing ops use `server.sh upgrade`
and friends. Never add ops behaviour here; if it isn't first-install glue,
it belongs in `server.sh`.

Backend listens on `:8787` and serves the frontend at `/` (NOT `/ui/` — it
used to, fixed in v0.3.1). CouchDB on `:5984`. Vaults are in `./vaults/`.

Running tests:
```
./.venv/bin/pytest backend/tests -q
```

## Conventions
- Python 3.11+, FastAPI, `ruff`, `mypy --strict`. Both are **blocking CI gates** (since v0.5.1) — run `ruff check backend && mypy --strict backend/app` before pushing.
- One project = one CouchDB DB + one vault dir + one Git repo. Never cross these.
- The app version lives in one place: `backend/app/__init__.py:__version__`. `main.py` and `/api/health` import it — never hardcode a version literal.
- Keep modules small and single-purpose; split only when a second consumer appears.
- Don't add features speculatively. If requirements unclear, ask.

## Common tasks
- **Add an endpoint**: add a route module under `backend/app/routes/` and register it in `backend/app/main.py`. Keep business logic in a sibling domain module.
- **Change commit cadence**: `backend/app/versioning.py` (`DEBOUNCE_SECONDS`).
- **Hermes invocation**: `backend/app/hermes.py` — the subprocess call is the one thing you tune per deployment.
- **Wisdom synthesis**: `backend/app/wisdom.py` — stub today (Git-log summariser); swap `_synthesise()` body for a real LLM pass later.
- **Search behaviour**: `backend/app/search.py` — SQLite FTS5 per project at `<vault>/.ckp/search.db`; bm25 with title column weighted 5×.
- **Stage promotion endpoint**: `backend/app/routes/stages_routes.py` — `POST /promote` (inbox → notes) and `POST /wisdom/synthesise`.
- **New project field**: update `backend/app/projects.py` model + the `/projects` view in `frontend/app.js`.
- **Anything that turns a user path into a vault file**: route it through `util.safe_path` (API) / `webdav._safe_path` (WebDAV). Never hand-roll a containment check.

## Gotchas
- Watcher + Git need to serialise writes to avoid racing commits (see `versioning.py` queue).
- Hermes output lands back in the vault → triggers the watcher again → commits. That's intended; don't try to suppress it.
- LiveSync sends many small revisions; debounce matters.
- The watcher MUST ignore non-mutating inotify events (`opened`, `closed`, `closed_no_write`). Reacting to them caused an infinite feedback loop via `search.update_file` (which reads the file and thus emits another `opened`) that prevented the commit debouncer from ever firing. See `_MUTATING` in `watcher.py`.
- Static assets (`styles.css`, `app.js`, …) are served from `/`, not `/ui/`. `index.html` uses relative paths; mounting at `/ui` would 404. `StaticFiles(html=True)` is mounted LAST so explicit API routes take precedence.
- Vault containment must use `Path.is_relative_to`, never a string-prefix compare. Sibling vaults can share a slug prefix (`proj-a` / `proj-a-secret`), so a prefix check lets a project token escape via `../`. This was the v0.5.1 traversal fix (`util.safe_path`); don't reintroduce the prefix pattern.
