#!/usr/bin/env bash
# Off-box snapshot of CKP state: every vault's Git repo + CouchDB dumps.
# Usage: ./scripts/backup.sh /path/to/backup-dir
set -euo pipefail

DEST="${1:-}"
if [ -z "$DEST" ]; then
  echo "usage: $0 <backup-dir>" >&2
  exit 2
fi
mkdir -p "$DEST"

cd "$(dirname "$0")/.."
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$DEST/ckp-$STAMP"
mkdir -p "$OUT"

# 1) Git bundles per project (compact, transportable, restoreable with git clone)
if [ -d vaults ]; then
  for proj in vaults/*/; do
    [ -d "$proj/.git" ] || continue
    name="$(basename "$proj")"
    git --git-dir "$proj/.git" bundle create "$OUT/vault-$name.bundle" --all
    echo "bundled $name"
  done
fi

# 2) CouchDB per-db JSON dumps (if couchdb is up)
COUCHDB_URL="${CKP_COUCHDB_URL:-http://admin:admin@127.0.0.1:5984}"
if curl -fs "$COUCHDB_URL/" >/dev/null 2>&1; then
  mkdir -p "$OUT/couchdb"
  for db in $(curl -fs "$COUCHDB_URL/_all_dbs" | tr -d '[]"' | tr ',' '\n'); do
    case "$db" in _*) continue;; esac
    curl -fs "$COUCHDB_URL/$db/_all_docs?include_docs=true" > "$OUT/couchdb/$db.json"
    echo "dumped couch db $db"
  done
else
  echo "note: couchdb not reachable at $COUCHDB_URL — skipping db dump" >&2
fi

# 3) Credentials + project registry
[ -f vaults/.registry.json ]   && cp vaults/.registry.json   "$OUT/"
[ -f vaults/.credentials.json ] && cp vaults/.credentials.json "$OUT/"

# 4) Tarball the snapshot
tar -C "$DEST" -czf "$DEST/ckp-$STAMP.tgz" "ckp-$STAMP"
rm -rf "$OUT"
echo "backup at $DEST/ckp-$STAMP.tgz"
