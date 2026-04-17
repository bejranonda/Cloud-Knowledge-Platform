# Knowledge Base

Running notes on *how this platform works internally* — derived from operating it, not from specs.

## Vault layout per project

```
vaults/<project>/
├── inbox/          # Raw "Info" — Hermes watches this
├── knowledge/      # Hermes output — structured "Knowledge"
├── notes/          # User-authored notes
└── .git/           # Managed by the versioner
```

## Commit cadence

- Debounce window: 2 s after last write (tunable in `config.py`).
- Author: `sync-bot <sync@platform.local>` unless `X-Sync-Source` header arrives from a known client → then author = device name.
- Message convention:
  - `sync: <device> @ <iso-ts>` for end-user changes.
  - `hermes: <source-file> -> knowledge/<out>` for pipeline output.
  - `manual: <user> via web-app` for Web-App edits.

## Hermes contract

- Invocation: `hermes-agent process --input <path> --output-dir <vault>/knowledge --project <slug>` (adjust to your Hermes build).
- Timeout: 120 s per Info file (override in project config).
- Failure: Hermes non-zero exit → job logged with stderr, no Knowledge file written, watcher continues.

## Graph generation

- Edges are extracted with regex `\[\[([^\]|#]+)` on each `.md`.
- Node id = relative path without extension.
- Cached in-memory; invalidated per project on any commit touching `.md`.

## Admin auth

- Set `CKP_ADMIN_TOKEN=<long-random>` in the backend env to enable.
- Dashboard stores the token in `localStorage` (via the 🔑 button in the header) and sends `Authorization: Bearer …` on mutating calls.
- WebDAV clients send the same token as the HTTP Basic password (username is ignored).
- `/api/health` reports `auth_required: true|false` so the UI can prompt on first load.

## SSE event bus

- `GET /api/events` emits: `fs` (project/path/op), `hermes` (status transitions), `project` (created). Keepalive comment every 20 s.
- The frontend re-fetches the tree and the open note when a matching `fs` event arrives and the buffer is clean.

## WebDAV vs LiveSync

- Both paths terminate in the same vault dir and go through the same watcher → search + versioning + SSE pipeline.
- Choose LiveSync for real-time + E2E + mobile tolerance; WebDAV for simplicity or when a client can't run LiveSync.

## Server lifecycle (one script)

All server-side operations are behind `scripts/server.sh` with subcommands:

| Subcommand | Purpose | Root? |
|---|---|---|
| `install` | Dev venv + deps + `docker compose up couchdb` | no |
| `start`   | Foreground uvicorn (dev) | no |
| `deploy`  | Production provision: apt deps, `ckp` system user, venv, systemd unit, Caddy, CouchDB | yes |
| `upgrade` | `git pull` + `pip install` + `systemctl restart ckp` | yes |
| `status`  | Health probes (backend, caddy, couchdb) + masked admin-token prefix | no |
| `backup <dir>` | Per-project git bundles + CouchDB `_all_docs` dumps + registry/credentials, tarred | no |
| `help`    | Print usage | no |

Previous scripts (`install.sh`, `start.sh`, `deploy-server.sh`, `backup.sh`)
were consolidated into this single dispatcher so operators only ever learn
one command surface.

## Per-project credentials

- `CKP_ADMIN_TOKEN` (env) is the bootstrap token. It can do anything.
- Admins issue **per-project tokens** via `POST /api/projects/{slug}/credentials`. Each token grants write access to one project (API + WebDAV). Tokens are persisted in `vaults/.credentials.json`.
- WebDAV clients use HTTP Basic with the project token as the password (username is ignored).
- Revoke via `DELETE /api/projects/{slug}/credentials?prefix=<first-6>`.

## Attachments

- Binary uploads go to `<vault>/attachments/`. Max 50 MB (`MAX_UPLOAD_BYTES` in `routes/attachments_routes.py`).
- Upload: `POST /api/projects/{slug}/attachments` (multipart `file`). Serve: `GET /api/projects/{slug}/attachments/{name}`.
- The frontend preview resolves `![[file.png]]` and markdown image paths against this endpoint.

## Multi-project isolation boundaries

| Layer | Mechanism |
|---|---|
| Storage | Separate CouchDB DB and vault dir |
| History | Separate Git repo |
| API | `/api/projects/{slug}/…` prefix + permission check |
| Hermes | Per-project working dir + env |
