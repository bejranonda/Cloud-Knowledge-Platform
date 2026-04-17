#!/usr/bin/env bash
# Install backend Python deps and start CouchDB via docker compose.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt

if command -v docker >/dev/null 2>&1; then
  docker compose up -d couchdb
  echo "CouchDB: http://127.0.0.1:5984 (admin/admin — change via env)"
else
  echo "WARN: docker not found. Install docker or run CouchDB yourself." >&2
fi

echo "Done. Run ./scripts/start.sh"
