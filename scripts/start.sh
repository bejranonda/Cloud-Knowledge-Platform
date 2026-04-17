#!/usr/bin/env bash
# Start the CKP backend (foreground).
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
[ -d .venv ] && . .venv/bin/activate

export PYTHONPATH="${PYTHONPATH:-}:$PWD/backend"
exec python -m uvicorn app.main:app \
  --app-dir backend \
  --host "${CKP_HOST:-0.0.0.0}" \
  --port "${CKP_PORT:-8787}"
