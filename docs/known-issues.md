# Known Issues

| # | Issue | Status | Workaround |
|---|---|---|---|
| 1 | LiveSync on iOS pauses when app backgrounded >30 s | Upstream | Enable *Periodic sync* as safety net |
| 2 | Very large attachments (>50 MB) slow down CouchDB replication | Open | Keep binaries out of vault, use `attachments/` symlink to object store |
| 3 | Git commits can race when two devices sync within the debounce window | Mitigated | 2 s debounce + commit queue serialises |
| 4 | Hermes agent sometimes holds a file lock on Windows-mounted vaults | Won't-fix (Linux-first) | Host the vault on ext4 on the server only |
| 5 | Graph view is O(N) per rebuild | Acceptable | Cache + incremental update on commit |
| 6 | WebDAV fallback does not carry end-to-end encryption metadata | By design | Use LiveSync as primary |
| 7 | Docs / CI automation referencing removed `install.sh` / `deploy-server.sh` / `backup.sh` directly | Resolved | All paths go through `scripts/server.sh <subcmd>` — update any personal runbooks |
| 8 | `server.sh deploy` and `server.sh upgrade` must be run as root; `install` and `start` must NOT | By design | The script self-checks with `id -u` and exits early |

File new issues in `docs/known-issues.md` with a date and reproduction path.
