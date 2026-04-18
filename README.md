# Cloud Knowledge Platform

A self-hosted PKM + sync gateway that replaces paid Obsidian Sync with a 100% free stack on Ubuntu. It synchronises Obsidian vaults across devices, versions every change in Git, exposes a Web-App for admin/data management, and dispatches new "Info" notes to the **Hermes Agent** which converts them into structured "Knowledge".

The pipeline is organised around the **DIKW-T** pyramid
(**D**ata → **I**nformation → **K**nowledge → **W**isdom + **T**ime) —
one folder per stage (`inbox/`, `notes/`, `knowledge/`, `wisdom/`), plus the
per-project Git repo as the time-series backbone. See
[docs/dikw-t.md](docs/dikw-t.md) for the authoritative model.

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
reference/    External blueprints (Honcho, Obsidian) — reconstruction-grade specs
business/     Project scope, stakeholders, success criteria
scripts/      install.sh / start.sh
docker-compose.yml   CouchDB + backend
```

## Quick start

```bash
./scripts/server.sh bootstrap  # one-shot from a bare Ubuntu: apt → install → start
# open http://<server>:8787/
```

Already have Docker + python3-venv? Use the shorter dev path:

```bash
./scripts/server.sh install    # venv + deps + CouchDB via docker compose
./scripts/server.sh start      # boot the FastAPI backend (foreground)
```

`scripts/server.sh` is the single entry point for all server-side lifecycle
operations: `bootstrap`, `install`, `start`, `deploy`, `upgrade`, `status`,
`backup`, `help`.

Client setup: see [docs/client-setup.md](docs/client-setup.md).
Architecture: see [docs/architecture.md](docs/architecture.md).

## Client onboarding

New users connecting Obsidian (desktop or mobile) to this platform should start with the
step-by-step guide at [docs/setup-client.md](docs/setup-client.md).
Technical users on macOS, Linux, or Windows can run the helper scripts in
[scripts/client/](scripts/client/) to pre-fill plugin settings automatically.

## Production deploy

For a hardened production install (systemd service, Caddy TLS, CouchDB in
Docker, idempotent deploy script) see **[docs/setup-server.md](docs/setup-server.md)**.

## Quickstarts

Role-specific guides for getting productive fast:

- [docs/quickstart-user.md](docs/quickstart-user.md) — end user who wants to take notes in Obsidian and have them sync automatically.
- [docs/quickstart-manager.md](docs/quickstart-manager.md) — team manager who creates projects, onboards teammates, and monitors Hermes output.
- [docs/quickstart-admin.md](docs/quickstart-admin.md) — server admin who owns the Ubuntu box, Docker, Caddy, and backups.

## Reverse-engineering references

The [`reference/`](reference/) folder contains **reconstruction-grade**
blueprints for the two external systems that most influenced this project:

- [`reference/honcho/`](reference/honcho/) — ambient personalisation,
  Conclusion/Representation/Dream pipeline, DIKW-T mapping.
- [`reference/obsidian/`](reference/obsidian/) — vault model, MetadataCache,
  LiveSync, headless CLI, failure modes.

Each `platform_blueprint.md` is complete enough that an AI given only that
file could stand up a working equivalent. See
[`reference/README.md`](reference/README.md) for a guided tour.

## Contributing

Before making non-trivial changes read **[docs/approach.md](docs/approach.md)** —
it's the decision playbook for this codebase.

## License
Internal / self-hosted use.
