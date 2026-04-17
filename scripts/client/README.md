# Client setup scripts

Helper scripts that pre-fill Obsidian plugin configuration for the Cloud Knowledge Platform,
so users do not have to hand-type connection details into the Obsidian UI.

---

## Scripts

### `setup-macos-linux.sh` — macOS and Linux

**What it does:**

- Prompts for (or accepts as positional arguments) the server URL, project slug,
  per-project token, local vault name, and sync method (`livesync` or `webdav`).
- Creates `~/Obsidian/<vault-name>/` if it does not already exist.
- Writes a pre-filled `data.json` into the correct plugin directory inside the vault:
  - LiveSync: `.obsidian/plugins/obsidian-livesync/data.json`
  - WebDAV:   `.obsidian/plugins/remotely-save/data.json`
- Skips the write if the config file already contains credentials (idempotent).
- Prints step-by-step next steps to complete setup inside Obsidian.

**How to run:**

```bash
# Interactive (prompts for each value)
bash scripts/client/setup-macos-linux.sh

# Non-interactive (all values as positional arguments)
bash scripts/client/setup-macos-linux.sh \
  https://ckp.example.com \
  team-wiki \
  mytoken123 \
  my-vault-name \
  webdav
```

Requirements: bash 4+, no sudo needed.

---

### `setup-windows.ps1` — Windows (PowerShell 5+)

**What it does:** Same logic as the bash script above, implemented in PowerShell.

- Accepts optional named parameters; prompts interactively for any that are missing.
- Token prompt uses `Read-Host -AsSecureString` so it is not echoed to the console.
- Creates `$HOME\Obsidian\<VaultName>\` if it does not already exist.
- Writes pre-filled `data.json` for the chosen plugin.
- Skips if credentials are already present (idempotent).

**How to run:**

```powershell
# Interactive
.\scripts\client\setup-windows.ps1

# Non-interactive
.\scripts\client\setup-windows.ps1 `
  -ServerUrl   https://ckp.example.com `
  -ProjectSlug team-wiki `
  -Token       mytoken123 `
  -VaultName   my-vault-name `
  -SyncMethod  webdav
```

If your execution policy blocks unsigned scripts, run once with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\client\setup-windows.ps1
```

Requirements: PowerShell 5 or later, no administrator rights needed.

---

## Disclaimer: mobile devices must be configured through the Obsidian app UI

**There is no automation path for iOS or Android.**

Obsidian on iOS and Android runs inside a sandboxed app container. The file system
that stores vault data and plugin configuration is not accessible from outside the app
— not via the Files app, not via ADB, and not via any script. There is no equivalent
of writing to `~/Obsidian/<vault>/.obsidian/plugins/` on mobile.

Mobile users must configure the sync plugin manually by following the step-by-step
instructions in [docs/setup-client.md](../../docs/setup-client.md), starting at
**Section 3 (LiveSync)** or **Section 4 (WebDAV)**.

---

## Security note

The scripts write the per-project token to a local file on disk:

```
~/Obsidian/<vault>/.obsidian/plugins/<plugin>/data.json
```

This is the same location Obsidian itself stores the token when you enter it through
the UI. Treat this directory with the same care as any credential store:

- Do not sync `.obsidian/plugins/` to a public repository.
- The scripts never print the token to stdout once it has been written.
- Tokens can be revoked at any time via the platform dashboard:
  Projects → your project → Credentials → Revoke.
