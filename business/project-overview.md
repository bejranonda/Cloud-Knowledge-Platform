# Business Overview

## Problem
Teams standardised on Obsidian for PKM but Obsidian Sync is a per-seat subscription, has only a 1-year history window, and offers no admin surface for multi-project governance or AI post-processing.

## Solution
A self-hosted platform on our Ubuntu cloud server that:
1. Replicates the Obsidian Sync UX for free (Self-hosted LiveSync + CouchDB).
2. Gives admins a Web-App to monitor sync, browse notes, and visualise the graph.
3. Preserves the full evolution of every project in Git.
4. Automates the *Info → Knowledge* conversion via the pre-installed Hermes Agent.

## Stakeholders
- **Admin** — owns the server, manages projects and credentials.
- **Authors** — end-users on PC / mobile; interact only with Obsidian.
- **Consumers** — read Knowledge via the Web-App or downstream systems.

## Success criteria
- Zero-cost per-seat sync for ≥ 20 devices.
- Median propagation (edit → visible on second device) < 3 s on LAN, < 10 s on 4G.
- Every change reproducible from Git history.
- Hermes processes new Info within 5 s of sync landing.
- Hard multi-project isolation: an authenticated user for project A cannot read B.
- Core flows (auth, note CRUD + commit, search, backlinks, history, WebDAV, attachments, per-project token scope, Hermes retrigger) validated by `pytest backend/tests` (10/10 passing as of v0.3.1).

## Out of scope (v1)
- Public sharing / read-only publish.
- SSO / SCIM.
- Mobile client of our own (Obsidian is the client).
