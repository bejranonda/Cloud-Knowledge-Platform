#!/usr/bin/env bash
# server.sh — single entry point for all server-side lifecycle operations.
#
# Usage:
#   ./scripts/server.sh install            # dev install: venv + deps + couchdb
#   ./scripts/server.sh start              # run backend in foreground (dev)
#   ./scripts/server.sh deploy             # production provision (sudo)
#   ./scripts/server.sh upgrade            # git pull + pip + systemctl restart (sudo)
#   ./scripts/server.sh status             # health probes
#   ./scripts/server.sh backup <dest-dir>  # snapshot git bundles + couchdb dumps
#   ./scripts/server.sh help
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$REPO_DIR/.env"
SERVICE_NAME="ckp"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
CADDY_FILE="/etc/caddy/Caddyfile"
VENV="$REPO_DIR/.venv"
CKP_USER="ckp"

die()  { echo "ERROR: $*" >&2; exit 1; }
log()  { echo "  $*"; }
step() { echo ""; echo "── $* ──"; }

require_root() {
  [ "$(id -u)" -eq 0 ] || die "run as root (sudo $0 $*)"
}

# ─────────────────────────────────────────────────────────────────────────────
# install — developer / first-time setup, no root required
# ─────────────────────────────────────────────────────────────────────────────
cmd_install() {
  cd "$REPO_DIR"

  step "Python venv + deps"
  # Ensure python3-venv is available (Ubuntu/Debian ships it separately)
  if ! python3 -c "import ensurepip" 2>/dev/null; then
    PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    log "python3-venv missing — attempting install (needs sudo)..."
    if command -v apt-get >/dev/null 2>&1; then
      sudo apt-get install -y -qq "python${PY_VER}-venv" python3-venv || \
        die "Could not install python3-venv. Run manually: sudo apt install python${PY_VER}-venv"
    else
      die "python3 venv unavailable. Install with your package manager (e.g. python${PY_VER}-venv)."
    fi
  fi
  python3 -m venv .venv
  # shellcheck disable=SC1091
  . .venv/bin/activate
  pip install --upgrade pip -q
  pip install -r backend/requirements.txt -q
  log "venv ready at $VENV"

  step "CouchDB via docker compose"
  if command -v docker >/dev/null 2>&1; then
    docker compose up -d couchdb
    log "CouchDB: http://127.0.0.1:5984 (admin/admin — change via env)"
  else
    log "WARN: docker not found. Install docker, or run CouchDB yourself."
  fi

  echo ""
  log "Done. Next: ./scripts/server.sh start"
}

# ─────────────────────────────────────────────────────────────────────────────
# start — foreground dev server
# ─────────────────────────────────────────────────────────────────────────────
cmd_start() {
  cd "$REPO_DIR"
  # shellcheck disable=SC1091
  [ -d .venv ] && . .venv/bin/activate

  export PYTHONPATH="${PYTHONPATH:-}:$REPO_DIR/backend"
  exec python -m uvicorn app.main:app \
    --app-dir backend \
    --host "${CKP_HOST:-0.0.0.0}" \
    --port "${CKP_PORT:-8787}"
}

# ─────────────────────────────────────────────────────────────────────────────
# deploy — production provisioning, idempotent, root only
# ─────────────────────────────────────────────────────────────────────────────
cmd_deploy() {
  require_root deploy

  step "Validate .env"
  [ -f "$ENV_FILE" ] || die ".env missing at $ENV_FILE. Create it with at minimum:
  CKP_ADMIN_TOKEN=\$(openssl rand -hex 32)
  COUCHDB_USER=admin
  COUCHDB_PASSWORD=changeme"
  grep -q 'CKP_ADMIN_TOKEN' "$ENV_FILE" || die "CKP_ADMIN_TOKEN missing in $ENV_FILE"
  log ".env OK"

  step "System packages"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq \
    python3 python3-venv git docker.io docker-compose-plugin \
    caddy curl ca-certificates
  systemctl enable --now docker >/dev/null 2>&1 || true
  log "installed"

  step "System user '$CKP_USER'"
  if ! id "$CKP_USER" &>/dev/null; then
    useradd --system --shell /usr/sbin/nologin --home-dir "$REPO_DIR" \
      --no-create-home "$CKP_USER"
    log "created"
  else
    log "already exists"
  fi
  usermod -aG docker "$CKP_USER" 2>/dev/null || true
  chown -R "${CKP_USER}:${CKP_USER}" "$REPO_DIR"

  step "Python venv + deps (as $CKP_USER)"
  if [ ! -x "$VENV/bin/python" ]; then
    sudo -u "$CKP_USER" python3 -m venv "$VENV"
  fi
  sudo -u "$CKP_USER" "$VENV/bin/pip" install --upgrade pip -q
  sudo -u "$CKP_USER" "$VENV/bin/pip" install -r "$REPO_DIR/backend/requirements.txt" -q

  step "systemd unit"
  install -m 644 "$REPO_DIR/deploy/systemd/ckp.service" "$SERVICE_FILE"
  systemctl daemon-reload
  systemctl enable "$SERVICE_NAME"
  systemctl restart "$SERVICE_NAME"

  step "Caddy"
  if [ ! -f "$CADDY_FILE" ] || ! grep -q 'reverse_proxy 127.0.0.1:8787' "$CADDY_FILE" 2>/dev/null; then
    install -m 644 "$REPO_DIR/deploy/caddy/Caddyfile" "$CADDY_FILE"
    log "Caddyfile installed — set CKP_DOMAIN before reloading in production"
  else
    log "existing CKP block detected — not overwriting"
  fi
  systemctl enable --now caddy >/dev/null 2>&1 || true
  systemctl reload caddy 2>/dev/null || systemctl restart caddy

  step "CouchDB container"
  docker compose -f "$REPO_DIR/docker-compose.yml" up -d couchdb

  cmd_status
}

# ─────────────────────────────────────────────────────────────────────────────
# upgrade — pull + reinstall + restart
# ─────────────────────────────────────────────────────────────────────────────
cmd_upgrade() {
  require_root upgrade
  cd "$REPO_DIR"
  step "git pull"
  sudo -u "$CKP_USER" git pull --ff-only
  step "pip install"
  sudo -u "$CKP_USER" "$VENV/bin/pip" install -r backend/requirements.txt -q
  step "systemctl restart $SERVICE_NAME"
  systemctl restart "$SERVICE_NAME"
  cmd_status
}

# ─────────────────────────────────────────────────────────────────────────────
# status — health probes
# ─────────────────────────────────────────────────────────────────────────────
cmd_status() {
  echo ""
  echo "════════════════════════════════════════════════"
  echo " Cloud Knowledge Platform — status"
  echo "════════════════════════════════════════════════"
  if command -v systemctl >/dev/null 2>&1; then
    echo " backend  : $(systemctl is-active $SERVICE_NAME 2>/dev/null || echo 'n/a')"
    echo " caddy    : $(systemctl is-active caddy 2>/dev/null || echo 'n/a')"
  fi
  if command -v docker >/dev/null 2>&1; then
    echo " couchdb  : $(docker inspect --format '{{.State.Status}}' ckp-couchdb 2>/dev/null || echo 'not running')"
  fi
  if [ -f "$ENV_FILE" ]; then
    masked="$(grep '^CKP_ADMIN_TOKEN' "$ENV_FILE" | cut -d= -f2- | cut -c1-8 || true)"
    [ -n "$masked" ] && echo " token    : ${masked}…  (first 8 chars)"
  fi
  echo " logs     : journalctl -u $SERVICE_NAME -f"
  echo "════════════════════════════════════════════════"
}

# ─────────────────────────────────────────────────────────────────────────────
# backup — per-project git bundles + couchdb json dumps + creds/registry
# ─────────────────────────────────────────────────────────────────────────────
cmd_backup() {
  local dest="${1:-}"
  [ -n "$dest" ] || die "usage: server.sh backup <dest-dir>"
  mkdir -p "$dest"
  cd "$REPO_DIR"
  local stamp out
  stamp="$(date +%Y%m%d-%H%M%S)"
  out="$dest/ckp-$stamp"
  mkdir -p "$out"

  step "git bundles"
  if [ -d vaults ]; then
    for proj in vaults/*/; do
      [ -d "$proj/.git" ] || continue
      name="$(basename "$proj")"
      git --git-dir "$proj/.git" bundle create "$out/vault-$name.bundle" --all
      log "bundled $name"
    done
  fi

  step "CouchDB dumps"
  local couch="${CKP_COUCHDB_URL:-http://admin:admin@127.0.0.1:5984}"
  if curl -fs "$couch/" >/dev/null 2>&1; then
    mkdir -p "$out/couchdb"
    for db in $(curl -fs "$couch/_all_dbs" | tr -d '[]"' | tr ',' '\n'); do
      case "$db" in _*) continue;; esac
      curl -fs "$couch/$db/_all_docs?include_docs=true" > "$out/couchdb/$db.json"
      log "dumped $db"
    done
  else
    log "couchdb not reachable — skipping"
  fi

  [ -f vaults/.registry.json ]    && cp vaults/.registry.json    "$out/"
  [ -f vaults/.credentials.json ] && cp vaults/.credentials.json "$out/"

  tar -C "$dest" -czf "$dest/ckp-$stamp.tgz" "ckp-$stamp"
  rm -rf "$out"
  echo ""
  log "backup at $dest/ckp-$stamp.tgz"
}

# ─────────────────────────────────────────────────────────────────────────────
# help
# ─────────────────────────────────────────────────────────────────────────────
cmd_help() {
  grep '^# ' "$0" | sed 's/^# //' | head -n 12
}

# ─────────────────────────────────────────────────────────────────────────────
# dispatch
# ─────────────────────────────────────────────────────────────────────────────
case "${1:-help}" in
  install)  shift; cmd_install  "$@";;
  start)    shift; cmd_start    "$@";;
  deploy)   shift; cmd_deploy   "$@";;
  upgrade)  shift; cmd_upgrade  "$@";;
  status)   shift; cmd_status   "$@";;
  backup)   shift; cmd_backup   "$@";;
  help|-h|--help) cmd_help;;
  *) echo "unknown subcommand: $1" >&2; cmd_help; exit 2;;
esac
