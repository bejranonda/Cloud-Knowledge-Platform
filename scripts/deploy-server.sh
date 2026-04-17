#!/usr/bin/env bash
# deploy-server.sh — Idempotent production deploy for Cloud Knowledge Platform.
# Run as root from /opt/ckp: sudo ./scripts/deploy-server.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$REPO_DIR/.env"
SERVICE_NAME="ckp"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
CADDY_FILE="/etc/caddy/Caddyfile"
VENV="$REPO_DIR/.venv"
CKP_USER="ckp"

# ── 0. Must be root ────────────────────────────────────────────────────────────
if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run as root (sudo $0)" >&2
  exit 1
fi

# ── 1. Validate .env ──────────────────────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE not found. Create it before running this script." >&2
  echo "  Minimal example:" >&2
  echo "    CKP_ADMIN_TOKEN=\$(openssl rand -hex 32)" >&2
  echo "    COUCHDB_USER=admin" >&2
  echo "    COUCHDB_PASSWORD=changeme" >&2
  exit 1
fi

if ! grep -q 'CKP_ADMIN_TOKEN' "$ENV_FILE"; then
  echo "ERROR: CKP_ADMIN_TOKEN not found in $ENV_FILE" >&2
  exit 1
fi

echo "[1/7] .env validated — CKP_ADMIN_TOKEN present"

# ── 2. Install system packages ─────────────────────────────────────────────────
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
  python3 python3-venv git docker.io docker-compose-plugin \
  caddy curl ca-certificates

# Ensure docker service is running
systemctl enable --now docker >/dev/null 2>&1 || true

echo "[2/7] System packages installed"

# ── 3. System user + ownership ────────────────────────────────────────────────
if ! id "$CKP_USER" &>/dev/null; then
  useradd --system --shell /usr/sbin/nologin --home-dir "$REPO_DIR" \
    --no-create-home "$CKP_USER"
  echo "  Created system user '$CKP_USER'"
fi

# Add ckp to docker group so it can start containers if needed
usermod -aG docker "$CKP_USER" 2>/dev/null || true

chown -R "${CKP_USER}:${CKP_USER}" "$REPO_DIR"
echo "[3/7] Ownership set: $REPO_DIR → $CKP_USER"

# ── 4. Python venv + deps ────────────────────────────────────────────────────
if [ ! -x "$VENV/bin/python" ]; then
  sudo -u "$CKP_USER" python3 -m venv "$VENV"
fi
sudo -u "$CKP_USER" "$VENV/bin/pip" install --upgrade pip -q
sudo -u "$CKP_USER" "$VENV/bin/pip" install -r "$REPO_DIR/backend/requirements.txt" -q
echo "[4/7] Python deps installed in $VENV"

# ── 5. systemd unit ───────────────────────────────────────────────────────────
install -m 644 "$REPO_DIR/deploy/systemd/ckp.service" "$SERVICE_FILE"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
echo "[5/7] systemd unit installed, enabled, and started"

# ── 6. Caddy configuration ────────────────────────────────────────────────────
if [ ! -f "$CADDY_FILE" ] || ! grep -q 'Cloud Knowledge Platform\|reverse_proxy 127.0.0.1:8787' "$CADDY_FILE" 2>/dev/null; then
  install -m 644 "$REPO_DIR/deploy/caddy/Caddyfile" "$CADDY_FILE"
  echo "  Caddyfile written to $CADDY_FILE"
  echo "  Set CKP_DOMAIN in $CADDY_FILE or in the Caddy environment before reloading."
else
  echo "  Caddyfile already contains a CKP block — skipping overwrite"
fi
systemctl enable --now caddy >/dev/null 2>&1 || true
systemctl reload caddy 2>/dev/null || systemctl restart caddy
echo "[6/7] Caddy configured and reloaded"

# ── 7. CouchDB via docker compose ────────────────────────────────────────────
docker compose -f "$REPO_DIR/docker-compose.yml" up -d couchdb
echo "[7/7] CouchDB container started"

# ── Summary ───────────────────────────────────────────────────────────────────
MASKED_TOKEN="$(grep 'CKP_ADMIN_TOKEN' "$ENV_FILE" | cut -d= -f2- | cut -c1-8)••••••••"

echo ""
echo "════════════════════════════════════════════════"
echo " Cloud Knowledge Platform — deploy complete"
echo "════════════════════════════════════════════════"
echo " Backend service : $(systemctl is-active $SERVICE_NAME)"
echo " Caddy           : $(systemctl is-active caddy)"
echo " CouchDB         : $(docker inspect --format '{{.State.Status}}' ckp-couchdb 2>/dev/null || echo 'unknown')"
echo " Dashboard       : https://\${CKP_DOMAIN:-<your-domain>}/"
echo " API base        : https://\${CKP_DOMAIN:-<your-domain>}/api/"
echo " CouchDB proxy   : https://\${CKP_DOMAIN:-<your-domain>}/couchdb/"
echo " Admin token     : $MASKED_TOKEN (first 8 chars shown)"
echo ""
echo " Edit domain:   $CADDY_FILE"
echo " Edit env vars: $ENV_FILE"
echo " View logs:     journalctl -u $SERVICE_NAME -f"
echo "════════════════════════════════════════════════"
