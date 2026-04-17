#!/usr/bin/env bash
# setup-macos-linux.sh
# Pre-fills Obsidian plugin config for Cloud Knowledge Platform sync.
# Supports: Self-hosted LiveSync and Remotely Save (WebDAV).
#
# Usage:
#   ./setup-macos-linux.sh [SERVER_URL] [PROJECT_SLUG] [TOKEN] [VAULT_NAME] [SYNC_METHOD]
#
# SYNC_METHOD: livesync | webdav
#
# All arguments are optional — the script will prompt for any that are missing.

set -euo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

info()    { printf '\033[0;34m[INFO]\033[0m  %s\n' "$*"; }
success() { printf '\033[0;32m[OK]\033[0m    %s\n' "$*"; }
warn()    { printf '\033[0;33m[WARN]\033[0m  %s\n' "$*"; }
error()   { printf '\033[0;31m[ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

prompt_if_empty() {
    local var_name="$1"
    local prompt_text="$2"
    local secret="${3:-no}"
    local current_val="${!var_name:-}"

    if [[ -z "$current_val" ]]; then
        if [[ "$secret" == "yes" ]]; then
            read -r -s -p "$prompt_text: " current_val
            echo
        else
            read -r -p "$prompt_text: " current_val
        fi
        [[ -z "$current_val" ]] && error "$var_name cannot be empty."
        printf -v "$var_name" '%s' "$current_val"
    fi
}

# ---------------------------------------------------------------------------
# Collect inputs (positional args or interactive prompts)
# ---------------------------------------------------------------------------

SERVER_URL="${1:-}"
PROJECT_SLUG="${2:-}"
TOKEN="${3:-}"
VAULT_NAME="${4:-}"
SYNC_METHOD="${5:-}"

prompt_if_empty SERVER_URL    "Server URL (e.g. https://ckp.example.com)"
prompt_if_empty PROJECT_SLUG  "Project slug (e.g. team-wiki)"
prompt_if_empty TOKEN         "Per-project token (from admin)" yes
prompt_if_empty VAULT_NAME    "Local vault name (folder will be ~/Obsidian/<name>)"

if [[ -z "$SYNC_METHOD" ]]; then
    read -r -p "Sync method [livesync|webdav] (default: webdav): " SYNC_METHOD
    SYNC_METHOD="${SYNC_METHOD:-webdav}"
fi

SYNC_METHOD="${SYNC_METHOD,,}"   # lowercase
[[ "$SYNC_METHOD" == "livesync" || "$SYNC_METHOD" == "webdav" ]] \
    || error "SYNC_METHOD must be 'livesync' or 'webdav', got: $SYNC_METHOD"

# Strip trailing slash from server URL for consistency
SERVER_URL="${SERVER_URL%/}"

# ---------------------------------------------------------------------------
# Locate / create the vault directory
# ---------------------------------------------------------------------------

VAULT_BASE="${HOME}/Obsidian"
VAULT_DIR="${VAULT_BASE}/${VAULT_NAME}"
OBSIDIAN_DIR="${VAULT_DIR}/.obsidian"

if [[ -d "$VAULT_DIR" ]]; then
    info "Vault directory already exists: $VAULT_DIR"
else
    info "Creating vault directory: $VAULT_DIR"
    mkdir -p "$VAULT_DIR"
fi

mkdir -p "${OBSIDIAN_DIR}/plugins"

# ---------------------------------------------------------------------------
# Write plugin config
# ---------------------------------------------------------------------------

if [[ "$SYNC_METHOD" == "livesync" ]]; then
    PLUGIN_ID="obsidian-livesync"
    PLUGIN_DIR="${OBSIDIAN_DIR}/plugins/${PLUGIN_ID}"
    CONFIG_FILE="${PLUGIN_DIR}/data.json"

    mkdir -p "$PLUGIN_DIR"

    if [[ -f "$CONFIG_FILE" ]]; then
        # Idempotency check: skip if couchDB URI is already set
        if grep -q '"couchDB_URI"' "$CONFIG_FILE" 2>/dev/null; then
            warn "Config already contains credentials: $CONFIG_FILE"
            warn "Skipping write to avoid overwriting existing settings."
            warn "Delete the file and re-run if you want to reset the configuration."
        else
            info "Config file exists but has no credentials — writing connection block."
            _WRITE_LIVESYNC=yes
        fi
    else
        _WRITE_LIVESYNC=yes
    fi

    if [[ "${_WRITE_LIVESYNC:-no}" == "yes" ]]; then
        info "Writing LiveSync config to: $CONFIG_FILE"
        cat > "$CONFIG_FILE" <<EOF
{
  "couchDB_URI": "${SERVER_URL}/couchdb/${PROJECT_SLUG}",
  "couchDB_USER": "",
  "couchDB_PASSWORD": "${TOKEN}",
  "couchDB_DBNAME": "${PROJECT_SLUG}",
  "liveSync": true,
  "syncOnStart": true,
  "encrypt": true
}
EOF
        # Note: couchDB_USER is intentionally left blank — the admin will confirm
        # the username separately. The token is written as the password.
        success "LiveSync config written."
    fi

else
    # WebDAV / Remotely Save
    PLUGIN_ID="remotely-save"
    PLUGIN_DIR="${OBSIDIAN_DIR}/plugins/${PLUGIN_ID}"
    CONFIG_FILE="${PLUGIN_DIR}/data.json"

    mkdir -p "$PLUGIN_DIR"

    if [[ -f "$CONFIG_FILE" ]]; then
        if grep -q '"address"' "$CONFIG_FILE" 2>/dev/null; then
            warn "Config already contains credentials: $CONFIG_FILE"
            warn "Skipping write to avoid overwriting existing settings."
            warn "Delete the file and re-run if you want to reset the configuration."
        else
            _WRITE_WEBDAV=yes
        fi
    else
        _WRITE_WEBDAV=yes
    fi

    if [[ "${_WRITE_WEBDAV:-no}" == "yes" ]]; then
        info "Writing Remotely Save (WebDAV) config to: $CONFIG_FILE"
        cat > "$CONFIG_FILE" <<EOF
{
  "s3": { "s3Endpoint": "", "s3Region": "", "s3AccessKeyID": "", "s3SecretAccessKey": "", "s3BucketName": "" },
  "webdav": {
    "address": "${SERVER_URL}/webdav/${PROJECT_SLUG}/",
    "username": "obsidian",
    "password": "${TOKEN}",
    "authType": "basic"
  },
  "dropbox": { "clientID": "", "clientSecret": "" },
  "onedrive": { "clientID": "", "clientSecret": "" },
  "serviceType": "webdav",
  "syncOnStartup": true,
  "autoRunEveryMilliseconds": 300000
}
EOF
        success "Remotely Save (WebDAV) config written."
    fi
fi

# ---------------------------------------------------------------------------
# Print next steps
# ---------------------------------------------------------------------------

echo
echo "========================================================"
echo "  Next steps"
echo "========================================================"
echo
echo "1. Open Obsidian."
echo "   If this vault does not appear automatically, choose:"
echo "   'Open folder as vault' → ${VAULT_DIR}"
echo
if [[ "$SYNC_METHOD" == "livesync" ]]; then
    echo "2. Go to Settings → Community plugins → Browse"
    echo "   Search for: Self-hosted LiveSync"
    echo "   Install and Enable it."
    echo
    echo "3. Open Settings → Self-hosted LiveSync → Remote Database"
    echo "   Verify the URI and credentials are pre-filled."
    echo "   Fill in the Username field that was left blank."
    echo "   URI: ${SERVER_URL}/couchdb/${PROJECT_SLUG}"
    echo
    echo "4. Set up E2E encryption under the Encryption tab"
    echo "   (use the shared passphrase your team agreed on)."
    echo
    echo "5. Click:"
    echo "   - 'Initialize database' if this is the FIRST device for this project."
    echo "   - 'Replicate' if another device has already been set up."
    echo
    echo "   WARNING: 'Initialize database' wipes the server DB."
    echo "   Only run it once, on the very first device."
else
    echo "2. Go to Settings → Community plugins → Browse"
    echo "   Search for: Remotely Save"
    echo "   Install and Enable it."
    echo
    echo "3. Open Settings → Remotely Save"
    echo "   Verify WebDAV address and credentials are pre-filled."
    echo "   Address: ${SERVER_URL}/webdav/${PROJECT_SLUG}/"
    echo
    echo "4. Click the cloud icon in the left sidebar (or"
    echo "   Settings → Remotely Save → Run sync now) to trigger"
    echo "   the first sync."
fi
echo
echo "For full instructions: docs/setup-client.md"
echo "========================================================"
