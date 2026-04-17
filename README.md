# Cloud Knowledge Platform

A self-hosted PKM + sync gateway that replaces paid Obsidian Sync with a 100% free stack on Ubuntu. It synchronises Obsidian vaults across devices, versions every change in Git, exposes a Web-App for admin/data management, and dispatches new "Info" notes to the **Hermes Agent** which converts them into structured "Knowledge".

## Capabilities

- **Self-hosted sync backend** (CouchDB, recommended) that mirrors the Obsidian Sync UX for PC and mobile.
- **Web-App dashboard** with connection monitor, note CRUD/browse, graph visualisation, and multi-project isolation.
- **Git-backed time-series history** — every synced change is committed so admins can replay evolution by step or timestamp.
- **Event-driven Hermes pipeline** — a file-system watcher fires Hermes on new Info and stores the produced Knowledge alongside.

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
