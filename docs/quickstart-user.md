# Quickstart: End User

You edit notes in Obsidian. They sync to the cloud automatically. That's it.

The platform stores your vault, versions every change in Git, and runs an AI
pipeline (Hermes) that turns raw notes you drop in `inbox/` into structured
knowledge in `knowledge/`.

---

## What you need before starting

From your admin, collect:

| Item | Example |
|---|---|
| Server URL | `https://notes.example.com` |
| Project slug | `team-alpha` |
| Your personal token | `ckp_abc123…` (treat like a password) |

You also need the **Obsidian** app on each device (PC, phone, tablet).

---

## Day 0 — 5-minute setup

Follow **[docs/setup-client.md](setup-client.md)** for the full plugin walkthrough.
The short version:

1. Open Obsidian → Settings → Community Plugins → search **Self-hosted LiveSync**
   → Install → Enable.
2. Settings → Self-hosted LiveSync → Remote Database:
   ```
   URI:      https://<server>/couchdb/<project-slug>
   Password: <your token>
   Database: <project-slug>
   ```
3. Enable the E2E passphrase your admin sent you.
4. Tap **Replicate**. First sync pulls the existing vault down.

> Prefer simplicity over real-time? Use **Remotely Save (WebDAV)** instead —
> see [docs/setup-client.md](setup-client.md) for that path.

---

## Day-to-day usage

### Where to put things

| Folder | Purpose |
|---|---|
| `notes/` | Your authored notes — write here by default. |
| `inbox/` | Quick captures. Hermes converts them into `knowledge/` automatically. |
| `knowledge/` | Hermes output — read-only from your perspective. |
| `attachments/` | Images and files — Obsidian manages this folder for you. |

Drop a quick thought:

```
inbox/2026-04-17-standup-idea.md
```

Within seconds the backend detects the new file, runs Hermes, and a structured
note appears in `knowledge/`. You'll see it in Obsidian on next sync.

### Linking and tagging

- Use `[[wikilinks]]` to connect notes. Links resolve across the whole project
  vault and appear in the graph view on the dashboard.
- Use `#tags` for grouping. The dashboard's Tags view aggregates them.

### Attachments

Drag an image into any note. Obsidian places it in `attachments/` and the sync
plugin treats it like any other file. Max size: **50 MB** per file.

---

## Checking what's on the cloud

Open the web dashboard at `https://<server>/` (plain root — not `/ui/`).

Click the **🔑** button in the header and paste your token. You can:

- Browse and read all notes in the file tree.
- See the wikilinks graph.
- View the full history of any note (History tab).
- Read Hermes job results (Hermes tab).

**Writes from the dashboard** (create, rename, delete, restore) require admin
credentials or an admin-granted write token. If you can only read, that's
expected — ask your admin if you need more.

---

## Common issues

**I see two copies of a note (conflict)**
LiveSync resolves conflicts automatically. If a duplicate with a suffix like
`_conflicted_copy` appears, open both, keep the one you want, and delete the
other. The next sync commits the resolution.

**Sync stopped on my phone**
Battery optimisation killed the app. Go to your phone's battery/power settings
and exempt Obsidian from optimization. See [docs/setup-client.md](setup-client.md)
for platform-specific steps.

**Note I just wrote isn't on the server yet**
LiveSync may be in Periodic mode. Pull down the sync icon in Obsidian to force
a manual sync, or wait for the next scheduled interval.

---

## Never do

- **Share your token.** It grants write access to the entire project. Each
  person should have their own token (ask your admin to issue one).
- **Commit secrets into notes.** The server Git-commits every change. Passwords,
  API keys, and personal data written in Markdown become part of the permanent
  history.

---

## Related reading

- [docs/quickstart-manager.md](quickstart-manager.md) — managing projects and teammates
- [docs/quickstart-admin.md](quickstart-admin.md) — server administration
- [docs/setup-client.md](setup-client.md) — full plugin installation walkthrough
- [docs/knowledge.md](knowledge.md) — vault layout, Hermes pipeline, attachments
