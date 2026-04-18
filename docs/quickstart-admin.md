# Quickstart: Server Admin

You own the Ubuntu box, Docker, Caddy/TLS, CouchDB, the CKP backend, the
Hermes Agent process, and backups. This guide covers daily operations,
incident response, and security. For the initial deploy, see
**[docs/setup-server.md](setup-server.md)**.

---

## What you own

| Layer | Your responsibility |
|---|---|
| Ubuntu + Docker | OS patches, Docker daemon, container restarts |
| Caddy / TLS | Reverse proxy config, certificate renewal |
| CouchDB | Database health, compaction, replication |
| CKP backend | FastAPI service, env vars, upgrades |
| Hermes Agent | Binary on PATH, model config, timeouts |
| Backups | Vault snapshots, off-box storage |

---

## First deploy

See **[docs/setup-server.md](setup-server.md)** for the full walkthrough. The
four-step summary:

```bash
git clone <repo> /opt/ckp && cd /opt/ckp
cp .env.example .env && $EDITOR .env   # set CKP_ADMIN_TOKEN and CouchDB creds
./scripts/server.sh deploy             # installs deps, starts Docker + backend
# point DNS A record to this box; Caddy handles TLS automatically
```

**Lab / dev boxes (no prereqs):** If the machine has nothing pre-installed, use
`bootstrap` instead of `deploy`. It installs all OS dependencies first, then runs
`install` and `start` for a local dev server:

```bash
sudo ./scripts/server.sh bootstrap
```

Use `deploy` for production (systemd service, Caddy TLS, `ckp` system user);
use `bootstrap` for throwaway dev environments only.

---

## Day-2 operations

### Health check

```bash
systemctl status ckp
curl -fs localhost:8787/api/health      # direct probe (bypasses Caddy/TLS)
curl https://<host>/api/health          # {"status":"ok","auth_required":true}
```

### Log tailing

```bash
journalctl -u ckp -f
```

### Backup

```bash
./scripts/server.sh backup /var/backups/ckp   # tarballs vaults/ + CouchDB data/
```

Schedule weekly via cron:

```cron
0 2 * * 0  root /opt/ckp/scripts/server.sh backup /var/backups/ckp
```

Copy the resulting archive off-box (S3, rsync to NAS, etc.) — local-only
backups don't protect against disk failure.

### Upgrade

```bash
systemctl stop ckp
git pull
.venv/bin/pip install -r backend/requirements.txt
systemctl start ckp
```

Check `journalctl -u ckp -f` after start to confirm clean boot.

### Rotate the admin token

```bash
# 1. Generate a new token (32+ random bytes)
openssl rand -hex 32

# 2. Update /opt/ckp/.env
CKP_ADMIN_TOKEN=<new-token>

# 3. Restart the service
systemctl restart ckp

# 4. Update the token in your password manager and re-paste into the dashboard
```

After rotation, existing per-project tokens remain valid (they are stored
separately in `vaults/.credentials.json`). Rotate project tokens only if you
suspect compromise.

---

## Emergency CLI access (when the web app is down)

Project state is plain files. Every vault is a Git repo:

```bash
cd /opt/ckp/vaults/<slug>

git log --oneline -20              # recent history
git show HEAD:notes/my-note.md     # read a specific revision
git restore --source=HEAD~3 notes/my-note.md  # roll back a file
```

Do **not** run `git reset --hard` without creating a backup branch first:

```bash
git branch backup/before-recovery && git reset --hard <sha>
```

---

## Watching health signals

| Signal | Where to look |
|---|---|
| Disk — vaults | `du -sh /opt/ckp/vaults/` — warn at 80 % of the mount |
| Disk — CouchDB | `du -sh /opt/ckp/data/couchdb/` |
| Backend memory | `systemctl status ckp` → memory field; the watcher + search index live in-process |
| Hermes queue depth | Dashboard → Hermes tab — many `pending` or `running` jobs signal a backlog |
| CouchDB | `docker ps` — container must show `healthy` |

---

## Common incidents

### "Dashboard returns 401"

`CKP_ADMIN_TOKEN` is missing or wrong in `.env`.

```bash
grep CKP_ADMIN_TOKEN /opt/ckp/.env   # must be set and non-empty
systemctl restart ckp
```

### "CouchDB unreachable"

```bash
docker ps                             # is the couchdb container running?
docker compose -f /opt/ckp/docker-compose.yml restart couchdb
journalctl -u ckp -f                 # watch backend reconnect
```

### "Hermes jobs stuck in `running`"

The Hermes binary is not on PATH for the `ckp` service user.

```bash
sudo -u ckp which hermes-agent        # should print a path
# If missing:
sudo ln -s /path/to/hermes-agent /usr/local/bin/hermes-agent
sudo -u ckp hermes-agent --version    # confirm it runs
systemctl restart ckp
```

Retry stuck jobs from the dashboard Hermes tab.

### "WebDAV 413 Request Entity Too Large"

Caddy's default body limit is rejecting large attachment uploads. Edit
`/etc/caddy/Caddyfile`:

```
route /webdav/* {
    request_body {
        max_size 100MB   # raise as needed; default CKP limit is 50MB
    }
    reverse_proxy localhost:8787
}
```

```bash
systemctl reload caddy
```

### "Git repo corrupted"

```bash
cd /opt/ckp/vaults/<slug>
git fsck                              # identify corruption
# If you have an off-box bundle backup:
git clone /path/to/backup/<slug>.bundle /tmp/<slug>-recovered
rsync -a /tmp/<slug>-recovered/ /opt/ckp/vaults/<slug>/
```

The backup script (`scripts/server.sh backup`) creates `.bundle` files. Verify your
backup schedule is running before you need this.

---

## Security checklist

- [ ] HTTPS enforced — Caddy terminates TLS; HTTP redirects to HTTPS.
- [ ] `CKP_ADMIN_TOKEN` is 32+ random bytes (`openssl rand -hex 32`).
- [ ] Firewall: only ports 80 and 443 open externally; 8787 and 5984 are
      loopback-only.
- [ ] CouchDB bound to `127.0.0.1` (not `0.0.0.0`) in `docker-compose.yml`.
- [ ] Backups stored off-box and verified quarterly with a test restore.
- [ ] `.env` is not world-readable: `chmod 600 /opt/ckp/.env`.
- [ ] OS and Docker updated on a monthly schedule.

---

## Related reading

- [docs/quickstart-user.md](quickstart-user.md) — end-user guide
- [docs/quickstart-manager.md](quickstart-manager.md) — project manager guide
- [docs/setup-server.md](setup-server.md) — full initial deploy walkthrough
- [docs/architecture.md](architecture.md) — component diagram and data flow
- [docs/knowledge.md](knowledge.md) — vault layout, credentials, SSE, WebDAV
- [docs/hermes-contract.md](hermes-contract.md) — Hermes invocation contract and config
- [docs/guidelines.md](guidelines.md) — engineering and operating conventions
