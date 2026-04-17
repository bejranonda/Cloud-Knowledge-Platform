# System Architecture

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

## 4. Why CouchDB over WebDAV

- LiveSync is transactional and resumable; WebDAV (Remotely Save) is polling + full-file PUTs.
- Conflict resolution is native (document revisions).
- Mobile-tolerant: background sync continues on flaky networks.
- Tradeoff: one extra process to run. Mitigated by docker-compose.

WebDAV remains a supported fallback for read-only mirror clients (see `docs/known-issues.md`).

## 5. Security boundaries

- CouchDB bound to localhost, reverse-proxied by Caddy/Nginx with HTTPS + Basic Auth per project user.
- Backend runs as unprivileged user; Hermes invoked with a restricted working dir.
- Git repos are local only by default; optional `git push` to private remote is per-project config.
