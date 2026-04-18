# Known Issues

| # | Issue | Status | Workaround | Resolved in |
|---|---|---|---|---|
| 1 | LiveSync on iOS pauses when app backgrounded >30 s | Upstream | Enable *Periodic sync* as safety net | — |
| 2 | Very large attachments (>50 MB) slow down CouchDB replication | Open | Keep binaries out of vault, use `attachments/` symlink to object store | — |
| 3 | Git commits can race when two devices sync within the debounce window | Mitigated | 2 s debounce + commit queue serialises | — |
| 4 | Hermes agent sometimes holds a file lock on Windows-mounted vaults | Won't-fix (Linux-first) | Host the vault on ext4 on the server only | — |
| 5 | Graph view is O(N) per rebuild | Acceptable | Cache + incremental update on commit | — |
| 6 | WebDAV fallback does not carry end-to-end encryption metadata | By design | Use LiveSync as primary | — |
| 7 | Docs / CI automation referencing removed `install.sh` / `deploy-server.sh` / `backup.sh` directly | Resolved | All paths go through `scripts/server.sh <subcmd>` — update any personal runbooks | — |
| 8 | `server.sh deploy` and `server.sh upgrade` must be run as root; `install` and `start` must NOT | By design | The script self-checks with `id -u` and exits early | — |
| 9 | Static assets (styles.css, app.js) returned 404 when `StaticFiles` was mounted at `/ui/` | Resolved | Mount at `/` with `html=True`; API/WebDAV routes registered first still take precedence | v0.3.1 |
| 10 | Git commits never fired from API writes — watcher feedback loop kept bumping debounce timestamp | Resolved | Watcher now filters to `_MUTATING` events only (created/modified/deleted/moved) | v0.3.1 |
| 11 | WebDAV LOCK returned 500 — `secrets` module not imported in `webdav.py` | Resolved | Import added | v0.3.1 |
| 12 | Two concurrent `POST /api/projects` could race and corrupt the registry | Resolved | Projects create() wrapped in `threading.Lock` | v0.3.1 |
| 13 | Search index is in-memory only — lost on backend restart | Open | Restart triggers a full re-index scan; no persistence yet | — |
| 14 | Log rotation not configured — `journalctl` storage grows unbounded | Open | Configure `SystemMaxUse` in `/etc/systemd/journald.conf` or add `logrotate` rule | — |
| 15 | CSRF protection not wired — state-changing API calls rely on Bearer token only | Open | Acceptable for Bearer-token APIs behind TLS; add CSRF middleware if browser cookies are ever used | — |
| 16 | Pre-DIKW vaults (created before v0.4) lack a `wisdom/` folder | Advisory | `mkdir -p vaults/<slug>/wisdom`; new projects get it automatically | v0.4 |
| 17 | `wisdom/` remains empty until a wisdom-capable Hermes build is wired up | Roadmap | Classifier + folder are ready; the synthesis pass is future work | — |
| 18 | Files outside the four stage folders are classified heuristically (frontmatter/wikilinks/hashtags) | By design | Normalise paths into a stage folder if strict classification is required | — |
| 19 | Our `hermes-agent process …` contract is stub-only — the real Hermes CLI (Nous Research) has no `process` subcommand | Advisory | Use the passthrough stub in `docs/hermes-contract.md`, or a wrapper script; see `reference/hermes/integration_notes.md` for the three migration paths | — |

File new issues in `docs/known-issues.md` with a date and reproduction path.

## See also

Generalised failure modes (MetadataCache staleness, binary-in-vault, mount-path
404, watcher feedback loop) are cross-referenced in
`reference/obsidian/platform_blueprint.md` §8.1. The items above are this
project's specific incident log; that section is the broader pattern
catalogue.
