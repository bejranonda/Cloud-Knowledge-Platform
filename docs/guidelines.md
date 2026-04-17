# Engineering Guidelines

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
- Watch `journalctl -u ckp-backend` for watcher/Git errors.
- `vaults/<proj>/.git` is the source of truth for history — never `git reset --hard` without a backup branch.
- CouchDB compaction weekly via cron (`scripts/compact.sh`).

## Change management
- Every backend change must update `docs/architecture.md` if it alters component boundaries.
- Bugs → `docs/known-issues.md` with date + repro.
- User-visible behaviour change → update README + `client-setup.md`.
