# Client Onboarding Guide

Step-by-step instructions for connecting Obsidian on any device — desktop (macOS, Linux, Windows)
or mobile (iOS, Android) — to the Cloud Knowledge Platform.

---

## 1. Prerequisites

Before you start, gather the following from your admin:

| Item | Where to find it |
|---|---|
| **Server URL** | e.g. `https://ckp.example.com` |
| **Project slug** | e.g. `team-wiki` — the short identifier for your vault |
| **Per-project token** | Dashboard → Projects → your project → Credentials |
| **Sync method** | Ask your admin: **LiveSync** or **WebDAV** |
| **E2E passphrase** (LiveSync only) | Shared out-of-band by your team |

> **Both sync methods work on every platform.** LiveSync (CouchDB) gives real-time,
> conflict-resolving, end-to-end encrypted sync. WebDAV (Remotely Save) is simpler and
> requires no CouchDB knowledge. Pick the one your team has standardised on — you can
> switch later without data loss since both paths write to the same server-side vault.

**Clock requirement**: Your device clock must be within **5 minutes** of the server.
LiveSync uses timestamps for conflict ordering; a skewed clock will cause spurious conflicts.
On macOS/Linux: `sudo ntpdate pool.ntp.org`. On Windows: Settings → Time & Language → Sync now.

---

## 2. Create or open your vault

### First device for this project

1. Open Obsidian.
2. Click **Create new vault**.
3. Name it anything you like (e.g. the project slug).
4. Choose a local folder (e.g. `~/Obsidian/team-wiki`).
5. Click **Create** — the vault is intentionally empty at this point; the plugin will
   populate it on first sync.

### Additional devices (vault already exists on the server)

Create an empty vault exactly as above. Do **not** copy files manually — the sync plugin
will pull the full vault from the server after you configure and trigger it.

![screenshot placeholder: Obsidian vault creation screen]

---

## 3. Path A — Self-hosted LiveSync (recommended for power users)

LiveSync uses CouchDB under the hood for real-time, bidirectional replication with
end-to-end encryption.

### 3.1 Install the plugin

1. In Obsidian, go to **Settings → Community plugins**.
2. Disable Safe Mode if prompted.
3. Click **Browse** and search for **Self-hosted LiveSync**.
4. Click **Install**, then **Enable**.

![screenshot placeholder: Community plugins browser showing Self-hosted LiveSync]

### 3.2 Configure Remote Database

1. Go to **Settings → Self-hosted LiveSync → Remote Database**.
2. Fill in the fields:

   | Field | Value |
   |---|---|
   | **URI** | `https://<server>/couchdb/<project-slug>` |
   | **Username** | Provided by admin |
   | **Password** | Provided by admin (per-project token) |
   | **Database name** | `<project-slug>` |

3. Click **Test** to verify connectivity. You should see a green success message.

![screenshot placeholder: LiveSync Remote Database settings panel]

### 3.3 Configure sync behaviour

1. Still in LiveSync settings, go to **Sync Settings**.
2. Set **Sync Mode** to **LiveSync** for real-time sync (recommended on desktop).
   On mobile, consider **Periodic + Sync on save** to preserve battery.
3. Enable **Sync on startup**.

### 3.4 Enable end-to-end encryption

1. Go to **Settings → Self-hosted LiveSync → End-to-end Encryption**.
2. Toggle **Enable end-to-end encryption** on.
3. Enter the shared **passphrase** your team agreed on out-of-band.
   Every device in this project must use the same passphrase — it is never sent to the server.

![screenshot placeholder: LiveSync E2E encryption settings]

### 3.5 Initialise or join the database

- **First device only**: Click **Initialize database**. This creates the CouchDB database
  on the server. Do this exactly once; repeating it wipes existing data.
- **Every subsequent device**: Click **Replicate** (not Initialize). The plugin will pull
  all existing notes from the server.

> If you accidentally click Initialize on a second device, contact your admin immediately.
> The Git-backed history on the server can be used to restore the vault.

---

## 4. Path B — Remotely Save (WebDAV)

Remotely Save uses the platform's built-in WebDAV endpoint. No CouchDB knowledge needed.

### 4.1 Install the plugin

1. Go to **Settings → Community plugins → Browse**.
2. Search for **Remotely Save**.
3. Click **Install**, then **Enable**.

![screenshot placeholder: Community plugins browser showing Remotely Save]

### 4.2 Configure WebDAV

1. Go to **Settings → Remotely Save**.
2. Set **Remote service** to **WebDAV**.
3. Fill in the fields:

   | Field | Value |
   |---|---|
   | **Server address** | `https://<server>/webdav/<project-slug>/` |
   | **Username** | Any non-empty string (e.g. `obsidian`) |
   | **Password** | Your per-project token (from admin) |
   | **Auth type** | Basic |

4. Click **Check** to test the connection. You should see "Great, the webdav server
   can be connected and the auth info is correct."

![screenshot placeholder: Remotely Save WebDAV settings panel]

### 4.3 Configure sync schedule

1. Enable **Sync on startup**.
2. Enable **Sync every N minutes** and set it to **5**.
3. On mobile (iOS/Android), also enable **Background auto sync** (see Section 5).

### 4.4 Trigger first sync

Click **Run sync** in the plugin ribbon (cloud icon in the left sidebar) or go to
**Settings → Remotely Save → Run sync now**. Wait for the status to change to "Finished."

---

## 5. Mobile gotchas

### iOS — battery optimisation

iOS aggressively suspends background processes. To keep Remotely Save or LiveSync running:

1. Go to **iOS Settings → General → Background App Refresh**.
2. Make sure **Obsidian** is toggled on.
3. In Remotely Save settings inside Obsidian, enable **Background auto sync**.
4. For LiveSync: set Sync Mode to **Periodic** with a 5-minute interval rather than
   full LiveSync mode, which is harder to sustain in iOS background.

> Note: True background sync on iOS is limited by the OS. You will always get a sync
> when you open Obsidian; background delivery is best-effort.

![screenshot placeholder: iOS Background App Refresh setting for Obsidian]

### Android — Doze mode

Android's Doze mode can delay background sync by minutes or hours. To exempt Obsidian:

1. Go to **Android Settings → Apps → Obsidian → Battery**.
2. Set battery usage to **Unrestricted** (label varies by manufacturer:
   "No restrictions", "Don't optimise", "Unrestricted").
3. In Remotely Save settings, enable **Background auto sync**.
4. Some manufacturers (Samsung, Xiaomi, Huawei) have an additional "Protected Apps"
   or "Auto-launch" list — add Obsidian there too.

![screenshot placeholder: Android battery optimisation settings for Obsidian]

### Clock skew warning

If either sync plugin reports errors referencing timestamps or shows repeated conflicts
on files you have not edited, check your device clock:

- iOS/Android: Settings → General (or Date & Time) → Set Automatically: **On**.
- The server and all clients must agree within **5 minutes**.

---

## 6. First sync sanity check

Once the plugin is configured and connected:

1. In Obsidian, create a new note at the path `inbox/hello.md`.
2. Type a line: `Hello from <your device name>`.
3. Save (Cmd/Ctrl+S, or it auto-saves).

**Expected result:**

- **LiveSync**: The note appears in the platform dashboard within ~10 seconds.
  Open `https://<server>/` in a browser, navigate to your project, and look for
  `inbox/hello.md` in the file tree.
- **WebDAV**: The note appears after the next sync cycle (up to 5 minutes, or
  immediately if you click **Run sync now**).

![screenshot placeholder: Platform dashboard showing inbox/hello.md in the file tree]

4. On a second device, confirm the note appears automatically (LiveSync) or after
   the next sync (WebDAV).
5. Delete the test note once you have confirmed sync is working.

---

## 7. Troubleshooting

### 401 Unauthorized

**Symptom**: Plugin shows "401" or "Unauthorized" during connection test or sync.

**Causes and fixes**:
- Wrong per-project token. Ask your admin to re-issue credentials via
  `POST /api/projects/{slug}/credentials` and give you the new token.
- For LiveSync: the *username* was also wrong. Double-check both username and password
  match what the admin provided — not the `CKP_ADMIN_TOKEN` env var itself but the
  per-project token they generated for you.
- Token was revoked. Ask admin to check `vaults/.credentials.json`.

### 403 Forbidden

**Symptom**: Connection succeeds but operations return 403.

**Cause**: Your token is valid but scoped to a different project, or admin-only
operations (e.g. Initialize) are blocked.

**Fix**: Confirm the project slug in the URL matches exactly the slug the admin created.
Slugs are case-sensitive.

### 404 Not Found

**Symptom**: Connection test fails with "404" or "Not found".

**Causes and fixes**:
- Project slug typo. Recheck the slug with your admin — e.g. `team-wiki` vs `teamwiki`.
- The project has not been created yet in the dashboard. Admin must create it first at
  `https://<server>/` → Projects → New project.
- Missing trailing slash on the WebDAV address. The address must end with `/`:
  `https://<server>/webdav/<project-slug>/`.

### Conflicts

**Symptom**: Obsidian shows conflicting versions of a note, or the dashboard shows
duplicate files with `.conflict` in the name.

**Causes and fixes**:
- Two devices edited the same note while offline. LiveSync will surface the conflict
  as a sibling document; Remotely Save may add a timestamped copy.
- Review both versions, merge manually, and delete the conflict copy.
- Avoid editing the same note on two devices simultaneously while offline.

### "Database not initialized" (LiveSync)

**Symptom**: LiveSync logs show "Database not found" or "Not initialized."

**Cause**: The `Initialize database` step was skipped on the first device, or you are
trying to connect to a project slug that does not yet have a CouchDB database.

**Fix**:
1. Confirm one device has run **Initialize database** (Settings → Self-hosted LiveSync →
   Remote Database → Initialize database).
2. All other devices should then click **Replicate**, not Initialize.
3. If you are the first user and Initialize fails with 404, ask your admin to confirm
   the project exists in the dashboard.

### Slow mobile sync

**Symptom**: Sync works but takes several minutes each time on mobile.

**Fixes**:
- Check battery optimisation settings (Section 5).
- On WebDAV, reduce the sync interval from 5 to 2 minutes in Remotely Save settings.
- On LiveSync, enable **Sync on startup** so at minimum every app open triggers a sync.
- Verify your mobile is on Wi-Fi — cellular data and VPNs can add latency.
- Check the server logs for slow CouchDB or WebDAV responses:
  `docker compose logs backend --tail 50`.

### Plugin not visible after install

**Symptom**: You installed the plugin but do not see its settings tab.

**Fix**: Go to **Settings → Community plugins** and ensure the plugin is toggled **on**
(the blue slider). Installing alone is not enough — you must also enable it.

---

## Appendix: Quick reference

### LiveSync connection values

```
URI:            https://<server>/couchdb/<project-slug>
Username:       <admin-provided>
Password:       <per-project token>
Database name:  <project-slug>
```

### WebDAV connection values

```
Server address: https://<server>/webdav/<project-slug>/
Username:       obsidian   (any non-empty string)
Password:       <per-project token>
Auth type:      Basic
```

### Platform dashboard

```
URL:  https://<server>/
```

Access it to verify sync is working, browse the file tree, view Git history,
and check Hermes pipeline jobs.
