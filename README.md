# Cloud Knowledge Platform

A self-hosted PKM + sync gateway that replaces paid Obsidian Sync with a 100% free stack on Ubuntu. It synchronises Obsidian vaults across devices, versions every change in Git, exposes a Web-App for admin/data management, and dispatches new "Info" notes to the **Hermes Agent** which converts them into structured "Knowledge".

## Capabilities

- **Two sync options**: Self-hosted LiveSync (CouchDB) for real-time E2E encrypted sync, **or** a built-in WebDAV endpoint for Obsidian Remotely Save — no CouchDB needed for the WebDAV path.
- **Obsidian-like Web-App**: three-pane editor with live Markdown preview, wikilinks, backlinks, tag browser, full-text search (Ctrl+K), force-directed graph, file tree with CRUD, dark theme.
- **Obsidian bridge**: reads `<vault>/.obsidian/` (workspace, starred, plugins, graph) and exposes it via API so the dashboard reflects what Obsidian sees.
- **Git-backed time-series history**: per-project repo, debounced commits, per-file history, unified diff view, one-click restore.
- **Event-driven Hermes pipeline**: watcher fires a worker queue with exponential-backoff retries; re-trigger from the UI.
- **Admin auth** (bearer token) and **live updates** over SSE.
- **Multi-project isolation**: separate CouchDB DB, vault dir, Git repo, Hermes workdir per project.

## Repo layout

```
backend/      FastAPI service (sync monitor, projects, graph, versioning, watcher, Hermes bridge)
frontend/     Static dashboard (no build step)
docs/         Architecture, client setup, knowledge base, known issues, guidelines
reference/    External references and comparison notes
business/     Project scope, stakeholders, success criteria
scripts/      install.sh / start.sh
docker-compose.yml   CouchDB + backend
```

## Quick start

```bash
./scripts/install.sh           # installs Python deps + CouchDB via docker compose
./scripts/start.sh             # boots CouchDB and the FastAPI backend
# open http://<server>:8787/
```

Client setup: see [docs/client-setup.md](docs/client-setup.md).
Architecture: see [docs/architecture.md](docs/architecture.md).

## License
Internal / self-hosted use.
