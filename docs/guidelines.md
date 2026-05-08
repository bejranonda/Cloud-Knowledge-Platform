# Engineering Guidelines

## Mental model (read this first)

Every file in a vault lives in exactly one **DIKW-T** stage:

| Stage | Folder | Writer |
|---|---|---|
| Data | `inbox/` | humans / ingest |
| Information | `notes/` | humans (curated) |
| Knowledge | `knowledge/` | Hermes |
| Wisdom + Time | `wisdom/` | Hermes wisdom mode, reading Git history |

When adding code, tests, or docs, state which stage(s) are affected. See `docs/dikw-t.md` for the framework and `/api/projects/{slug}/dikw` for the runtime view.

## Code
- Python 3.11+, FastAPI, async where it buys something, sync where it's simpler.
- No premature abstractions: keep each module < ~300 lines; split only when a second consumer appears.
- Type-hint every public function; run `ruff` + `mypy --strict` on backend.
- Secrets only via env vars (`CKP_*`) — never commit `.env`.

## Adding a project
1. `POST /api/projects` with `{slug, display_name}`.
2. Backend: creates CouchDB DB, vault dir, Git repo, Hermes workdir.
3. Issue credentials via dashboard; share passphrase out-of-band.

## Operating
- Watch `journalctl -u ckp -f` for watcher/Git errors.
- `vaults/<proj>/.git` is the source of truth for history — never `git reset --hard` without a backup branch.
- Use `scripts/server.sh <subcmd>` for *every* lifecycle operation. Do not re-introduce per-concern scripts; add a new subcommand instead.
- CouchDB compaction weekly via cron; see `scripts/server.sh backup` for the scheduled companion job.
- The watcher must only react to mutating events (`created`, `modified`, `deleted`, `moved`); ignoring `opened`/`closed` is load-bearing — reacting to them causes a search-read → open-event feedback loop that prevents the debounced commit from ever firing.

## Frontend
- Static assets are served from `/`; do not re-mount to `/ui/`. `index.html` uses relative paths so the mount point must be `/` with `html=True`, with `/api/*` and `/webdav/*` routes registered first to retain precedence.

## Change management
- Every backend change must update `docs/architecture.md` if it alters component boundaries.
- Any change that moves files between DIKW-T stages (or introduces a new stage) must update `docs/dikw-t.md`.
- Bugs → `docs/known-issues.md` with date + repro.
- User-visible behaviour change → update README + `client-setup.md`.

## Reference material

- `reference/` holds reverse-engineering-grade blueprints for Honcho and
  Obsidian. Use them when designing features that echo those systems; cite
  the specific section (`reference/<vendor>/<file>.md` §N) in PR
  descriptions so the lineage is visible.
- Do **not** edit files under `reference/` to reflect our own changes — they
  describe the external systems, not ours. Update `docs/` for project-side
  changes; update `reference/` only when the external system itself changes
  or when we've verified a technical detail about it.
- `reference/README.md` is the tour. Start there when the folder is new to
  you.

## Continuous validation
- After any non-trivial change run `./.venv/bin/pytest backend/tests -q` until green twice in a row.
- The full suite now includes frontend smoke tests (`test_frontend.py`) that verify the static bundle is served and `app.js` passes `node --check`. Keep them lightweight — deeper UI tests wait until the UI stabilises.
- `grep -r "Info → Knowledge" docs/ || true` should be empty — the canonical phrasing is the full DIKW-T chain.
- `grep -rn "inbox/\|notes/\|knowledge/\|wisdom/" docs/ business/ reference/` sanity-checks that docs describe all four stages, not a subset.
