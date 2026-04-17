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

## Multi-project isolation boundaries

| Layer | Mechanism |
|---|---|
| Storage | Separate CouchDB DB and vault dir |
| History | Separate Git repo |
| API | `/api/projects/{slug}/…` prefix + permission check |
| Hermes | Per-project working dir + env |
