# Client-side setup

End-users run standard Obsidian. One community plugin gives them the self-hosted sync experience.

## Recommended: Self-hosted LiveSync

Plugin: **Self-hosted LiveSync** by vrtmrz (Community Plugins → search "Self-hosted LiveSync").

1. Install & enable the plugin in Obsidian.
2. Settings → Self-hosted LiveSync → **Remote Database configuration**:
   - URI: `https://<your-server>/couchdb/<project-slug>`
   - Username / Password: issued by the admin (see Web-App → Projects → Credentials).
   - Database name: `<project-slug>`
3. **Sync Settings**: enable *LiveSync* for real-time; otherwise *Periodic* + *Sync on save* for mobile battery.
4. **End-to-end encryption**: strongly recommended. Generate the passphrase in the Web-App; all devices of the same project must share it.
5. First run: tap **Initialize database** (only on the first device) then **Replicate** on every other device.

## Alternate: Remotely Save (WebDAV, built into this backend)

This server speaks WebDAV directly at `/webdav/<project-slug>/` — no CouchDB
needed. Use this when LiveSync is blocked, or as the primary sync for
lightweight devices.

1. Install **Remotely Save** in Obsidian.
2. Service: **WebDAV**.
3. Address: `https://<your-server>/webdav/<project-slug>/`
4. Username: anything (e.g. `admin`).
5. Password: your `CKP_ADMIN_TOKEN` (the backend accepts the same token via HTTP Basic).
6. Enable *Sync on startup* and *Sync every N minutes*.

All WebDAV writes are versioned in Git and re-indexed for search the same
way LiveSync writes are.

## Device checklist

- [ ] Same project slug and passphrase on every device.
- [ ] Clock within 5 minutes of server (LiveSync uses it for conflict ordering).
- [ ] Mobile: disable battery optimisation for Obsidian to allow background LiveSync.
