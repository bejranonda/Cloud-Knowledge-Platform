# Quickstart: Project Manager / Owner

You run one or more projects on the platform but you don't own the server.
Your responsibilities: project lifecycle, teammate credentials, reviewing
Hermes output, and watching activity. Escalate infrastructure issues to the
server admin.

---

## Getting access

The server admin gives you `CKP_ADMIN_TOKEN` (or a scoped equivalent).

1. Open the dashboard at `https://<server>/`.
2. Click the **🔑** button in the header.
3. Paste your token and confirm. The UI stores it in `localStorage` for the
   session. You now have full write access through the dashboard.

---

## Creating a project

Dashboard → **Projects** tab → fill in:

| Field | Notes |
|---|---|
| Slug | URL-safe, lowercase, no spaces — e.g. `team-alpha`. Permanent. |
| Display name | Human-readable — e.g. "Team Alpha Q2 Notes". |

Click **Create**. The backend provisions:

- A CouchDB database for LiveSync replication.
- A vault directory (`vaults/<slug>/`) with `inbox/`, `knowledge/`, `notes/`.
- A Git repository for full history.
- A Hermes working directory for AI jobs.

The project appears immediately in the Projects list.

---

## Onboarding a teammate

1. Projects tab → open the project → **Credentials** tab.
2. Click **Issue new token**.
3. **Copy the token immediately** — it is shown only once and cannot be
   recovered (only revoked).
4. Send the teammate:
   - Server URL: `https://<server>/`
   - Project slug: `<slug>`
   - Their token
   - Link to **[docs/setup-client.md](setup-client.md)**

Each teammate should have their own token. Never share tokens.

---

## Revoking access

Credentials tab → find the token by its first-6-character prefix → click
**Revoke**. The token is invalid immediately; the next sync attempt from that
device will fail with 401.

Issue a fresh token if the person needs continued access (e.g. after a lost
device).

---

## Watching activity

### Sync tab

Shows which devices have connected and when. Stale devices that haven't synced
in >24 h appear greyed out — useful for spotting a team member whose sync broke.

### History tab

Every change is a Git commit. Commit messages follow the convention:

```
sync: <device-name> @ <iso-timestamp>   ← end-user edits
hermes: <inbox-file> -> knowledge/<out> ← AI pipeline output
manual: <user> via web-app              ← dashboard edits
```

Click any commit to see the diff. Click **Restore** to roll a file back to that
point (the restore itself becomes a new commit — nothing is lost).

### Hermes tab

Lists all AI conversion jobs for the project. Statuses:

| Status | Meaning |
|---|---|
| `pending` | Queued, not yet started. |
| `running` | In progress (timeout: 120 s). |
| `done` | Output written to `knowledge/`. |
| `failed` | Non-zero exit from Hermes. Click to see stderr. Use **Retry** to re-run. |

If you see persistent `failed` jobs, check that the source file in `inbox/` is
valid Markdown and escalate to the server admin if Hermes itself appears broken.

---

## Curating the vault

- **Tags view** — see every `#tag` used across the project. Click a tag to list
  notes.
- **Dashboard editor** — rename, move, or delete notes directly. All changes are
  Git-committed with message `manual: <user> via web-app`.
- **Graph view** — spot orphan notes (no `[[wikilinks]]` pointing to them) and
  connect them.

Prefer dashboard edits over asking users to move files manually — it keeps
history clean and atomic.

---

## When to escalate to the server admin

- Dashboard is unreachable or returns 5xx errors.
- Disk usage warnings (visible in dashboard footer or server monitoring).
- Upgrading the platform to a new version.
- Adding or changing the Hermes AI model (`CKP_HERMES_BIN`).
- Needing a project deleted permanently (the backend soft-archives; the admin
  purges from disk).
- CouchDB errors in the Sync tab that don't resolve within a few minutes.

---

## Related reading

- [docs/quickstart-user.md](quickstart-user.md) — end-user note-taking guide
- [docs/quickstart-admin.md](quickstart-admin.md) — server administration
- [docs/setup-client.md](setup-client.md) — plugin installation for teammates
- [docs/knowledge.md](knowledge.md) — vault layout, credentials, per-project isolation
- [docs/hermes-contract.md](hermes-contract.md) — how Hermes converts Info → Knowledge
