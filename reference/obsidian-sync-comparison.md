# Reference: Obsidian Sync vs. Self-hosted LiveSync

| Feature | Obsidian Sync (paid) | Self-hosted LiveSync + this platform |
|---|---|---|
| Real-time sync | Yes | Yes (CouchDB `_changes`) |
| E2E encryption | Yes | Yes (plugin-side passphrase) |
| Version history | 1 yr (paid tier) | Unlimited, Git-backed, per-commit |
| Mobile | iOS / Android | iOS / Android (same plugin) |
| Cost | $8–$10 / mo / user | Server cost only |
| Conflict resolution | Automatic | Automatic (CouchDB revisions) |
| Admin UI | None (per-vault settings) | Web-App dashboard, multi-project |
| Content staging | None | **DIKW-T** pyramid: Data / Information / Knowledge / Wisdom |
| AI post-processing | None | Hermes Agent pipeline (stage promotion + wisdom mode) |
| Time-series reasoning | None | Per-project Git repo is first-class; `wisdom/` folder explains *why* things changed |

## External links

- Obsidian Sync: https://obsidian.md/sync
- Self-hosted LiveSync: https://github.com/vrtmrz/obsidian-livesync
- Remotely Save (WebDAV fallback): https://github.com/remotely-save/remotely-save
- CouchDB: https://couchdb.apache.org/
- DIKW pyramid (background): https://en.wikipedia.org/wiki/DIKW_pyramid
