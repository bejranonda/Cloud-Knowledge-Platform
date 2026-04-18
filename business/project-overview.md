# Business Overview

## Problem
Teams standardised on Obsidian for PKM but Obsidian Sync is a per-seat subscription, has only a 1-year history window, and offers no admin surface for multi-project governance or AI post-processing. More importantly, it has no notion of *stage* — every file is just a file, so raw captures, curated notes, and synthesised knowledge blur together, and there is no way to reason about *why* a project's knowledge changed over time.

## Solution
A self-hosted platform on our Ubuntu cloud server organised around the **DIKW-T pyramid** — **D**ata, **I**nformation, **K**nowledge, **W**isdom, plus **T**ime:

1. Replicates the Obsidian Sync UX for free (Self-hosted LiveSync + CouchDB).
2. Gives admins a Web-App to monitor sync, browse notes, visualise the graph, and see the DIKW-T stage breakdown per project.
3. Preserves the full evolution of every project in Git — the **Time** axis is a first-class property, not an afterthought.
4. Automates stage progression via the pre-installed **Hermes Agent**: Data (`inbox/`) → Information (`notes/`) → Knowledge (`knowledge/`) → Wisdom (`wisdom/`, time-series reasoning over Git history).

See [docs/dikw-t.md](../docs/dikw-t.md) for the authoritative framework, and
[reference/](../reference/) for the external blueprints (Honcho, Obsidian)
that informed the design.

## Stakeholders
- **Admin** — owns the server, manages projects and credentials.
- **Authors** — end-users on PC / mobile; capture Data and curate Information in Obsidian.
- **Consumers** — read synthesised Knowledge and Wisdom via the Web-App or downstream systems.

## Success criteria
- Zero-cost per-seat sync for ≥ 20 devices.
- Median propagation (edit → visible on second device) < 3 s on LAN, < 10 s on 4G.
- Every change reproducible from Git history; every file classifiable into a DIKW-T stage.
- Hermes promotes new Data/Information within 5 s of sync landing.
- Hard multi-project isolation: an authenticated user for project A cannot read B.
- `/api/projects/{slug}/dikw` returns accurate stage counts for any vault.
- Core flows (auth, note CRUD + commit, search, backlinks, history, WebDAV, attachments, per-project token scope, Hermes retrigger, DIKW summary) validated by `pytest backend/tests`.

## Out of scope (v1)
- Public sharing / read-only publish.
- SSO / SCIM.
- Mobile client of our own (Obsidian is the client).
- Cross-project Wisdom (time-series reasoning is per-project only).
