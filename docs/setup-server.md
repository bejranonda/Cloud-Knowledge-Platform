# Server Setup Guide

Operator-grade walkthrough for deploying Cloud Knowledge Platform (CKP) on a
fresh Ubuntu server. Assumes a competent sysadmin; commands are copy-pasteable.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| **OS** | Ubuntu 22.04 LTS or 24.04 LTS (64-bit) |
| **Domain** | A-record pointing to the server's public IP (e.g. `ckp.example.com`) |
| **Ports** | 80 and 443 open inbound (Caddy / Let's Encrypt); 8787 and 5984 should be **closed** externally |
| **User** | A user with `sudo` access; the script creates a dedicated `ckp` system account |
| **Docker** | Docker CE + Docker Compose plugin (`docker compose`) |
| **Python** | 3.11 or newer (`python3 --version`) |
| **Git** | 2.x (`git --version`) |

The deploy script (`scripts/server.sh deploy`) will install any missing packages
via `apt-get`, so you only need a working Ubuntu system with `sudo`.

---

## Step 1 — Clone and provision

```bash
sudo git clone https://github.com/your-org/Cloud-Knowledge-Platform /opt/ckp
# Or copy the repo from your workstation:
# sudo rsync -a . root@server:/opt/ckp/

# The deploy script will set ownership; pre-set it now so the git clone is readable:
sudo chown -R $USER /opt/ckp
```

If the server already has the repo, skip the clone and just pull:

```bash
cd /opt/ckp && sudo git pull
```

---

## Step 2 — Create the environment file

CKP is configured entirely through environment variables loaded from `/opt/ckp/.env`.
Create it now — **before** running the deploy script.

```bash
sudo tee /opt/ckp/.env > /dev/null <<EOF
# ── Required ────────────────────────────────────────────────
# Secret token for admin API calls. Generate a new one each deployment.
CKP_ADMIN_TOKEN=$(openssl rand -hex 32)

# CouchDB credentials (must match docker-compose.yml at startup).
COUCHDB_USER=admin
COUCHDB_PASSWORD=$(openssl rand -base64 18 | tr -d '=+/')

# ── Optional overrides ──────────────────────────────────────
# Public-facing domain (used by Caddyfile).
# CKP_DOMAIN=ckp.example.com

# Where vaults are stored on disk (default: /opt/ckp/vaults).
# CKP_VAULTS_ROOT=/opt/ckp/vaults

# CouchDB URL used internally by the backend.
# CKP_COUCHDB_URL=http://admin:changeme@127.0.0.1:5984

# Path (or name on PATH) of the Hermes Agent binary.
# CKP_HERMES_BIN=hermes-agent

# Per-file Hermes timeout in seconds (default 120).
# CKP_HERMES_TIMEOUT=120

# Git commit debounce window in seconds (default 2.0).
# CKP_COMMIT_DEBOUNCE=2.0

# Git author identity written into vault commit history.
# CKP_GIT_AUTHOR=sync-bot
# CKP_GIT_EMAIL=sync@platform.local
EOF
sudo chmod 600 /opt/ckp/.env
```

**Variable reference** (see `backend/app/config.py` for the canonical list):

| Variable | Default | Purpose |
|---|---|---|
| `CKP_ADMIN_TOKEN` | *(none)* | Bearer token required for all write API calls. |
| `COUCHDB_USER` | `admin` | CouchDB admin username (also read by `docker-compose.yml`). |
| `COUCHDB_PASSWORD` | `admin` | CouchDB admin password. Change before first run. |
| `CKP_DOMAIN` | — | Your public domain; used in the Caddyfile template. |
| `CKP_VAULTS_ROOT` | `./vaults` | Filesystem root for all vault directories. |
| `CKP_COUCHDB_URL` | `http://admin:admin@127.0.0.1:5984` | Full URL the backend uses to talk to CouchDB. Update if you change `COUCHDB_USER`/`COUCHDB_PASSWORD`. |
| `CKP_HERMES_BIN` | `hermes-agent` | Path or binary name of the Hermes Agent executable. |
| `CKP_HERMES_TIMEOUT` | `120` | Seconds before a Hermes subprocess is killed. |
| `CKP_COMMIT_DEBOUNCE` | `2.0` | Debounce window in seconds before committing filesystem events. |
| `CKP_GIT_AUTHOR` | `sync-bot` | Git author name recorded in vault history commits. |
| `CKP_GIT_EMAIL` | `sync@platform.local` | Git author email recorded in vault history commits. |

> **Tip**: after changing `.env`, restart the backend with
> `sudo systemctl restart ckp`.

---

## Step 3 — Run the deploy script

```bash
cd /opt/ckp
sudo ./scripts/server.sh deploy
```

The script is **idempotent** — re-running it is safe. It performs these steps in order:

1. Validates that `.env` exists and contains `CKP_ADMIN_TOKEN`.
2. Installs system packages: `python3`, `python3-venv`, `git`, `docker.io`,
   `docker-compose-plugin`, `caddy`, `curl` (skips packages already present).
3. Creates the `ckp` system user (no login shell, home at `/opt/ckp`) if missing.
4. Installs Python dependencies into `/opt/ckp/.venv` as the `ckp` user.
5. Writes `/etc/systemd/system/ckp.service`, reloads systemd, then enables and
   starts the service.
6. Writes `/etc/caddy/Caddyfile` (only if the file does not already contain a
   CKP block), then reloads Caddy.
7. Starts the CouchDB Docker container via `docker compose up -d couchdb`.
8. Prints a summary: service statuses, URLs, and a masked admin token.

Expected final output:

```
════════════════════════════════════════════════
 Cloud Knowledge Platform — deploy complete
════════════════════════════════════════════════
 Backend service : active
 Caddy           : active
 CouchDB         : running
 Dashboard       : https://<your-domain>/
 API base        : https://<your-domain>/api/
 CouchDB proxy   : https://<your-domain>/couchdb/
 Admin token     : a3f9b2c1••••••••  (first 8 chars shown)
...
════════════════════════════════════════════════
```

---

## Step 4 — TLS / reverse proxy (Caddy)

Caddy handles HTTPS automatically via Let's Encrypt — no `certbot` needed.

The Caddyfile installed to `/etc/caddy/Caddyfile` uses a placeholder domain.
Set your domain in one of two ways:

**Option A — Edit the Caddyfile directly:**

```bash
sudo nano /etc/caddy/Caddyfile
# Replace {$CKP_DOMAIN:example.com} with your actual domain, e.g.:
#   ckp.example.com {
sudo systemctl reload caddy
```

**Option B — Set `CKP_DOMAIN` in the Caddy environment** (keeps the template reusable):

```bash
# /etc/caddy/Caddyfile stays as-is; add to Caddy's environment:
sudo systemctl edit caddy --force
# Add under [Service]:
#   Environment="CKP_DOMAIN=ckp.example.com"
sudo systemctl restart caddy
```

The Caddyfile at `deploy/caddy/Caddyfile` (reference copy in the repo):

```
{$CKP_DOMAIN:example.com} {
    encode zstd gzip

    request_body {
        max_size 100MB
    }

    # CouchDB replication for Obsidian Self-hosted LiveSync
    handle_path /couchdb/* {
        reverse_proxy 127.0.0.1:5984
    }

    # Backend (API + WebDAV + UI)
    reverse_proxy 127.0.0.1:8787
}
```

**Important — large attachment uploads**: The `request_body { max_size 100MB }`
directive raises Caddy's body limit above the default, which is required for
WebDAV `PUT` of large attachments (PDFs, images, audio). If you need more than
100 MB, increase the value or set `max_size 0` to remove the cap.

WebDAV methods (`PROPFIND`, `MKCOL`, `MOVE`, `COPY`, `LOCK`, `UNLOCK`) pass
through to the backend automatically — Caddy forwards all HTTP methods.

---

## Step 5 — Install Hermes Agent

Hermes is an optional AI pipeline that converts "Info" notes into structured
"Knowledge" entries. See [`docs/hermes-contract.md`](hermes-contract.md) for
the full invocation contract.

**To enable:**

1. Install the Hermes binary (e.g. `/usr/local/bin/hermes-agent`).
2. Add to `/opt/ckp/.env`:

```bash
CKP_HERMES_BIN=/usr/local/bin/hermes-agent
# Optionally raise the timeout for large notes:
CKP_HERMES_TIMEOUT=300
```

3. Restart the backend:

```bash
sudo systemctl restart ckp
```

**Testing without a real Hermes build** — deploy the minimal stub from
`docs/hermes-contract.md`:

```bash
sudo tee /usr/local/bin/hermes-agent > /dev/null <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
INPUT=""; OUT=""; PROJECT=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --input) INPUT="$2"; shift 2;;
    --output-dir) OUT="$2"; shift 2;;
    --project) PROJECT="$2"; shift 2;;
    process) shift;;
    *) shift;;
  esac
done
name=$(basename "$INPUT" .md)
{ echo "# Knowledge: ${name}"; echo; cat "$INPUT"; } > "$OUT/${name}.md"
STUB
sudo chmod +x /usr/local/bin/hermes-agent
```

---

## Step 6 — Create the first project and test the admin API

Replace `ckp.example.com` with your actual domain. Load the token from `.env`:

```bash
TOKEN=$(sudo grep CKP_ADMIN_TOKEN /opt/ckp/.env | cut -d= -f2-)

# Create a project
curl -fsS \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST https://ckp.example.com/api/projects \
  -d '{"slug":"team","display_name":"Team"}'
```

Expected response:

```json
{"slug": "team", "display_name": "Team", "created_at": "..."}
```

**Issue a device token** (for Obsidian LiveSync / Remotely Save):

```bash
curl -fsS \
  -H "Authorization: Bearer $TOKEN" \
  -X POST https://ckp.example.com/api/projects/team/credentials
```

Record the returned credentials. Each Obsidian client needs its own credential
set — see [`docs/client-setup.md`](client-setup.md) for plugin configuration.

**Dashboard**: open `https://ckp.example.com/` in a browser. The three-pane
editor, graph view, and Hermes job log are all accessible there.

---

## Step 7 — Backups

Add a weekly cron job to snapshot vaults (Git bundles) and CouchDB:

```bash
sudo crontab -e
# Add the following line:
0 2 * * 0 /opt/ckp/scripts/server.sh backup /var/backups/ckp >> /var/log/ckp-backup.log 2>&1
```

The backup script (`scripts/server.sh backup`) creates a timestamped `.tgz` archive
containing:
- One Git bundle per project (compact, restorable with `git clone`).
- CouchDB JSON exports of all user databases.
- `vaults/.registry.json` and `vaults/.credentials.json`.

Verify a backup and list its contents:

```bash
ls -lh /var/backups/ckp/
tar -tzf /var/backups/ckp/ckp-<timestamp>.tgz | head -30
```

To restore a vault bundle:

```bash
git clone /var/backups/ckp/ckp-<ts>/vault-team.bundle /opt/ckp/vaults/team
```

---

## Step 8 — Upgrade path

```bash
# 1. Stop the service
sudo systemctl stop ckp

# 2. Pull latest code (as root or the deploying user)
cd /opt/ckp && sudo git pull

# 3. Install any new Python dependencies
sudo -u ckp /opt/ckp/.venv/bin/pip install -r /opt/ckp/backend/requirements.txt -q

# 4. Re-apply any updated systemd or Caddy config if changed upstream
sudo install -m 644 /opt/ckp/deploy/systemd/ckp.service /etc/systemd/system/ckp.service
sudo systemctl daemon-reload

# 5. Restart
sudo systemctl start ckp
sudo systemctl status ckp
```

For zero-downtime upgrades, consider running two instances behind Caddy and
doing a rolling swap — but for a self-hosted single-tenant install, the brief
downtime during restart is usually acceptable.

---

## Troubleshooting

**1. Backend service fails to start**

```bash
journalctl -u ckp -n 50 --no-pager
```

Common causes: missing `.env`, syntax error in `.env` (bare `$` not escaped),
Python import error. Check the log for the exact traceback.

**2. 401 Unauthorized on every API call**

Verify the token you're sending matches `CKP_ADMIN_TOKEN` in `.env`:

```bash
sudo grep CKP_ADMIN_TOKEN /opt/ckp/.env
curl -H "Authorization: Bearer <token>" https://ckp.example.com/api/projects
```

Tokens are compared byte-for-byte; watch for trailing newlines if you set the
var with `echo` instead of `printf`.

**3. CouchDB not reachable / 502 on `/couchdb/`**

```bash
docker ps | grep ckp-couchdb
docker logs ckp-couchdb --tail 30
# If the container is stopped:
docker compose -f /opt/ckp/docker-compose.yml up -d couchdb
```

Also confirm `CKP_COUCHDB_URL` in `.env` uses the credentials from
`COUCHDB_USER`/`COUCHDB_PASSWORD`.

**4. WebDAV returns 413 on large file uploads**

The Caddyfile `request_body { max_size 100MB }` block is missing or too small.
Edit `/etc/caddy/Caddyfile`, increase the value, then `sudo systemctl reload caddy`.

**5. Hermes jobs are stuck / always retrying**

```bash
# Check the binary is executable and on the configured path
sudo -u ckp /usr/local/bin/hermes-agent --help 2>&1 | head -5
# Review the backend log for the subprocess stderr
journalctl -u ckp -n 100 | grep -i hermes
```

Also check `CKP_HERMES_TIMEOUT` — if processing takes longer than the timeout,
the backend kills the subprocess and marks the job failed.

**6. Git commit author shows wrong name/email**

Set `CKP_GIT_AUTHOR` and `CKP_GIT_EMAIL` in `.env`, then restart:

```bash
sudo systemctl restart ckp
```

These variables control the `--author` argument passed to every vault commit.

**7. Caddy not obtaining a TLS certificate (Let's Encrypt fails)**

Ensure port 80 is reachable from the internet (used for ACME HTTP-01 challenge)
and that the A-record for your domain resolves to this server:

```bash
dig +short ckp.example.com
curl -v http://ckp.example.com/.well-known/acme-challenge/test
journalctl -u caddy -n 50 | grep -i 'acme\|tls\|cert'
```

**8. Service starts but dashboard is blank / assets 404**

Confirm `WorkingDirectory` in the service unit is `/opt/ckp` and the `frontend/`
directory exists there. The backend serves static files from a path relative to
the working directory:

```bash
ls /opt/ckp/frontend/
sudo systemctl status ckp
```

**9. `docker compose` command not found**

The deploy script installs `docker-compose-plugin` (the `compose` subcommand of
Docker CLI). If you installed Docker differently, install the plugin manually:

```bash
sudo apt-get install -y docker-compose-plugin
docker compose version
```

**10. Permission denied writing to `vaults/` or `data/`**

The hardened service unit restricts writes to `ReadWritePaths=/opt/ckp/vaults /opt/ckp/data`.
Both directories must be owned by `ckp`:

```bash
sudo chown -R ckp:ckp /opt/ckp/vaults /opt/ckp/data
sudo systemctl restart ckp
```
