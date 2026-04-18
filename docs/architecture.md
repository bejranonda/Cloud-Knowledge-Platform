# System Architecture

The conceptual model is the **DIKW-T pyramid** — Data, Information, Knowledge,
Wisdom + Time. Each stage is a vault folder (`inbox/`, `notes/`,
`knowledge/`, `wisdom/`) and the per-project Git repo provides the time-series
backbone. See [dikw-t.md](dikw-t.md) for the framework, folder conventions,
and the `/api/projects/{slug}/dikw` endpoint. This document covers the
runtime components that move files between those stages.

## 1. High-level diagram

```
┌──────────────┐         ┌──────────────┐        ┌──────────────┐
│  Obsidian PC │         │Obsidian iOS  │        │Obsidian And. │
│  + LiveSync  │         │ + LiveSync   │        │ + LiveSync   │
└──────┬───────┘         └──────┬───────┘        └──────┬───────┘
       │ HTTPS (CouchDB replication protocol)          │
       └──────────────────────┬───────────────────────┘
                              ▼
                 ┌────────────────────────┐
                 │  CouchDB (per-project) │   <-- self-hosted "Obsidian Sync"
                 └───────────┬────────────┘
                             │ _changes feed (continuous)
                             ▼
     ┌─────────────────────────────────────────────────────┐
     │           Cloud Knowledge Platform Backend          │
     │                    (FastAPI)                        │
     │                                                     │
     │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
     │  │ Projects │  │ Sync Mon │  │ Graph builder    │   │
     │  └──────────┘  └──────────┘  └──────────────────┘   │
     │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
     │  │ Watcher  │  │ Git Ver. │  │ Hermes dispatcher│   │
     │  └─────┬────┘  └────┬─────┘  └────────┬─────────┘   │
     └────────┼────────────┼─────────────────┼─────────────┘
              ▼            ▼                 ▼
       ┌───────────┐ ┌──────────────┐ ┌───────────────┐
       │ Vault FS  │ │ Git repo(s)  │ │ Hermes Agent  │
       │ (master)  │ │ per project  │ │ (local exec)  │
       └───────────┘ └──────────────┘ └───────────────┘
                                             │
                                             ▼
                                     Knowledge/*.md
                                     (written back to vault)
```

## 2. Component responsibilities

| Component | Purpose |
|---|---|
| **CouchDB** | Stores the canonical vault as JSON docs; speaks the replication protocol that Obsidian LiveSync uses on every client. One DB per project for isolation. |
| **CouchDB → FS materialiser** | The backend subscribes to the `_changes` feed and writes the current state of each note to `vaults/<project>/` on disk so Obsidian-on-server and Hermes can read plain Markdown. |
| **Watcher** | `watchdog` observes `vaults/<project>/inbox/` (Info) and fires Hermes; observes the whole vault and fires the Git committer. |
| **Git versioner** | Each project has its own Git repo co-located with the vault. Commits are batched (debounced ~2 s) with author = sync source + timestamp message. |
| **Hermes dispatcher** | Subprocess invocation of the pre-installed Hermes Agent with the new Info file, capturing stdout/stderr and writing the result to `vaults/<project>/knowledge/`. |
| **Web-App** | FastAPI + static dashboard. Serves sync status, note browser/editor, graph (wikilinks → nodes/edges), history timeline, Hermes job log. |
| **Project isolation** | Separation enforced at: CouchDB database, vault directory, Git repo, Hermes working dir. API paths are `/projects/{slug}/…`. |

## 3. Data flow (single change)

1. User edits note on phone → LiveSync replicates to CouchDB.
2. Backend `_changes` listener receives revision, writes file to `vaults/<proj>/…`.
3. Watcher debounce fires → Git versioner commits with message `sync: <device> @ <iso-ts>`.
4. If the file landed under `inbox/`, Hermes dispatcher runs; output written to `knowledge/` which re-triggers steps 2–3 → commit `hermes: knowledge for <file>`.
5. Dashboard SSE stream pushes the new commit + Hermes job to any open browser.

## 4. Sync paths: LiveSync (primary) vs. WebDAV (alternate)

Two first-class options; users pick per-project:

- **Self-hosted LiveSync (CouchDB)** — real-time, E2E encrypted, conflict-resolving, mobile-tolerant.
- **WebDAV endpoint at `/webdav/{project}/`** — built into this backend (`backend/app/webdav.py`). Obsidian *Remotely Save* points directly here; no CouchDB required. Every write from WebDAV also triggers versioning + search reindex + SSE event, so the two paths are interchangeable from the backend's perspective.

## 5. Obsidian bridge

The Ubuntu server has Obsidian installed. We do not drive the GUI; instead
`backend/app/obsidian_bridge.py` reads `<vault>/.obsidian/*.json` (workspace,
starred/bookmarks, graph settings, enabled plugins, daily-notes,
templates) and exposes them via `/api/projects/{slug}/obsidian/*`. The
Web-App uses this to show recent files, starred items, and plugin state
without duplicating Obsidian's data model.

## 5. Security boundaries

- CouchDB bound to localhost, reverse-proxied by Caddy/Nginx with HTTPS + Basic Auth per project user.
- Backend runs as unprivileged user; Hermes invoked with a restricted working dir.
- Admin mutations (create project, write/delete/move note, restore, Hermes retrigger, WebDAV writes) require `Authorization: Bearer <CKP_ADMIN_TOKEN>` when the env var is set. WebDAV additionally accepts the same token as HTTP Basic password.
- SSE stream (`/api/events`) is read-only and carries fs / hermes / project events.
- Git repos are local only by default; optional `git push` to private remote is per-project config.
