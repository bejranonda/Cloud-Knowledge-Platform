# Knowledge Base

Running notes on *how this platform works internally* — derived from operating it, not from specs.

## Vault layout per project — DIKW-T

The folder layout is the [DIKW-T pyramid](dikw-t.md) in concrete form:

```
vaults/<project>/
├── inbox/          # [Data]        Raw capture — Hermes watches this
├── notes/          # [Information] Tagged + linked notes, human-authored
├── knowledge/      # [Knowledge]   Hermes output (evergreen / synthesised)
├── wisdom/         # [Wisdom + T]  Hermes wisdom mode: why things changed
├── attachments/    # Binary uploads (images, PDFs, …)
└── .git/           # The Time axis — managed by the versioner
```

Runtime stage breakdown: `GET /api/projects/{slug}/dikw` returns counts per
stage plus Git commit stats. Classifier lives in `backend/app/dikw.py`.

## Commit cadence

- Debounce window: 2 s after last write (tunable in `config.py`).
- Author: `sync-bot <sync@platform.local>` unless `X-Sync-Source` header arrives from a known client → then author = device name.
- Message convention:
  - `sync: <device> @ <iso-ts>` for end-user changes.
  - `hermes: <stage-in> -> <stage-out> (<source> -> <out>)` for pipeline output, e.g. `hermes: information -> knowledge (notes/foo.md -> knowledge/foo.md)`.
  - `manual: <user> via web-app` for Web-App edits.

## Hermes contract — stage promotion

Hermes is the **stage-promotion engine**. The watcher feeds it any new file in
`inbox/` or `notes/` (Data / Information) and it writes synthesised output to
`knowledge/`. A future wisdom-mode pass reads the Git history of `knowledge/`
and writes to `wisdom/`.

- Invocation: `hermes-agent process --input <path> --output-dir <vault>/knowledge --project <slug>` (adjust to your Hermes build). See `docs/hermes-contract.md`.
- Timeout: 120 s per source file (override in project config).
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
| `bootstrap` | Installs all OS-level prerequisites (python3, python3-venv, git, docker.io, docker-compose-plugin, curl, openssl) via apt, then chains `install` → `start`. Suitable for bare Ubuntu dev boxes with nothing pre-installed. | yes |
| `install` | Dev venv + deps + `docker compose up couchdb` | no |
| `start`   | Foreground uvicorn (dev) | no |
| `deploy`  | Production provision: apt deps, `ckp` system user, venv, systemd unit, Caddy, CouchDB | yes |
| `upgrade` | `git pull` + `pip install` + `systemctl restart ckp` | yes |
| `status`  | Health probes (backend, caddy, couchdb) + masked admin-token prefix | no |
| `backup <dir>` | Per-project git bundles + CouchDB `_all_docs` dumps + registry/credentials, tarred | no |
| `help`    | Print usage | no |

## v0.3.1 fixes & behaviour

**Watcher feedback-loop fix.** Prior to v0.3.1 the filesystem watcher reacted to
all watchdog events including non-mutating ones (`opened`, `closed`,
`closed_no_write`). `search.update_file()` reads the file on each event, which
causes further `opened` events — creating an infinite feedback loop that
continually bumped `last_event_ts` and prevented the debounced commit worker from
ever firing. The fix: `watcher.py` now defines `_MUTATING = {created, modified,
deleted, moved}` and ignores all other event types. Git commits from API writes now
fire correctly.

**Static asset mount.** Prior to v0.3.1, `StaticFiles` was mounted at `/ui/` but
`index.html` used relative paths, so `styles.css`, `app.js`, `icon.svg`, and
`manifest.webmanifest` returned 404. Fixed by mounting at `/` with `html=True`.
`/api/*` and `/webdav/*` routes still take precedence because they are registered
first. The dashboard is served from `https://<server>/` (plain root).

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

## External references (reconstruction-grade)

The `reference/` folder carries self-contained blueprints for the two external
systems that shape this platform: **Honcho** (ambient personalisation) and
**Obsidian** (local-first PKM). Each `platform_blueprint.md` is complete
enough that an AI given only that file can rebuild a working equivalent. We
keep them because (a) if either upstream disappears we can still ship, and
(b) their design patterns routinely inform our own code.

Notable mappings and take-aways worth knowing:

- **Honcho ↔ DIKW-T.** `reference/honcho/platform_blueprint.md` §8.2 maps
  Honcho's Conclusions → our `notes/` (Information), Representations →
  `knowledge/`, Dream consolidation → `wisdom/`. Parallel is exact.
- **Obsidian failure modes.** `reference/obsidian/platform_blueprint.md` §8.1
  is the generalised form of our `docs/known-issues.md`: watcher feedback
  loop, MetadataCache staleness, mount-path 404, large-binary-in-vault.
- **LiveSync decision.** `reference/obsidian/obsidian-sync-comparison.md` is
  the table we cite when asked *why CouchDB + LiveSync* instead of an
  object-store + WebDAV-only design.
- **Hermes ↔ DIKW-T.** `reference/hermes/platform_blueprint.md` §8 maps the
  real Hermes Agent's agent loop, skill store, and session FTS5 onto our
  Data/Information/Knowledge/Wisdom folders. §4 (Learning Loop) is the
  pattern to copy if we ever want an endogenous Wisdom producer.
- **Hermes integration reality.** `reference/hermes/integration_notes.md`
  flags that the upstream Hermes CLI has no `process` subcommand — our
  `CKP_HERMES_BIN` contract only works against the stub in
  `docs/hermes-contract.md` or a wrapper script. Three migration paths are
  documented there.

Tour: `reference/README.md`.

## DIKW-T classifier

`backend/app/dikw.py` classifies every `.md` in a vault into `data`,
`information`, `knowledge`, or `wisdom`. Rules:

1. Top-level folder wins: `inbox/` → Data, `notes/` → Information (with
   heuristic fallback to Data if no structure), `knowledge/` → Knowledge,
   `wisdom/` → Wisdom.
2. "Structure" = YAML frontmatter, a `[[wikilink]]`, or a `#tag`. Anything
   without structure outside the four stage folders is Data.

The classifier is pure, cheap, and re-runs on every `/dikw` summary request —
no index to maintain.

## Stage promotion + Wisdom synthesis

- `POST /api/projects/{slug}/promote` — moves a Data file from `inbox/` into
  `notes/` with minimal frontmatter (`title`, optional `tags`,
  `promoted_from`, `stage: information`). Knowledge promotion is still
  Hermes's job; we don't promote to `knowledge/` by hand.
- `POST /api/projects/{slug}/wisdom/synthesise` — runs the deterministic
  wisdom stub (`backend/app/wisdom.py`) over the project's `knowledge/`
  folder and writes `wisdom/<stem>.md` for every knowledge file with ≥ 2
  commits. Idempotent. The body of `_synthesise()` is a commit-chain
  summary today; swap for a real LLM pass (Hermes wisdom mode) later.

UI surfaces both: the editor toolbar shows a **Promote ↑** button on inbox
files; the DIKW dashboard has a **Synthesise Wisdom ↻** button.

## Search — persistent FTS5

Per-project SQLite FTS5 at `<vault>/.ckp/search.db` (WAL mode,
`unicode61` tokenizer with diacritic stripping). Survives restart. BM25
scoring with title column weighted 5× over body. Reindex happens at startup
(`watcher.start()` calls `search.reindex()` per project) and incrementally
on every mutating watcher event. `.ckp/` is in the watcher ignore list so
index writes never trigger commits or re-processing.
