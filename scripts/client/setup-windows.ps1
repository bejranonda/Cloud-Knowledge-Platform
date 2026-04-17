# setup-windows.ps1
# Pre-fills Obsidian plugin config for Cloud Knowledge Platform sync.
# Supports: Self-hosted LiveSync and Remotely Save (WebDAV).
#
# Usage (run in PowerShell 5+):
#   .\setup-windows.ps1 [-ServerUrl <url>] [-ProjectSlug <slug>] [-Token <token>]
#                       [-VaultName <name>] [-SyncMethod <livesync|webdav>]
#
# All parameters are optional — the script will prompt for any that are missing.

#Requires -Version 5

[CmdletBinding()]
param(
    [string]$ServerUrl    = "",
    [string]$ProjectSlug  = "",
    [string]$Token        = "",
    [string]$VaultName    = "",
    [string]$SyncMethod   = ""
)

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-Info    { param($Msg) Write-Host "[INFO]  $Msg" -ForegroundColor Blue }
function Write-Ok      { param($Msg) Write-Host "[OK]    $Msg" -ForegroundColor Green }
function Write-Warn    { param($Msg) Write-Host "[WARN]  $Msg" -ForegroundColor Yellow }
function Write-Err     { param($Msg) Write-Error "[ERROR] $Msg" }

function Prompt-IfEmpty {
    param(
        [string]$Value,
        [string]$PromptText,
        [switch]$Secret
    )
    if ([string]::IsNullOrWhiteSpace($Value)) {
        if ($Secret) {
            $secure = Read-Host -Prompt $PromptText -AsSecureString
            $bstr   = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
            $Value  = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
            [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        } else {
            $Value = Read-Host -Prompt $PromptText
        }
        if ([string]::IsNullOrWhiteSpace($Value)) {
            Write-Err "$PromptText cannot be empty."
        }
    }
    return $Value
}

# ---------------------------------------------------------------------------
# Collect inputs
# ---------------------------------------------------------------------------

$ServerUrl   = Prompt-IfEmpty $ServerUrl   "Server URL (e.g. https://ckp.example.com)"
$ProjectSlug = Prompt-IfEmpty $ProjectSlug "Project slug (e.g. team-wiki)"
$Token       = Prompt-IfEmpty $Token       "Per-project token (from admin)" -Secret
$VaultName   = Prompt-IfEmpty $VaultName   "Local vault name (folder will be $HOME\Obsidian\<name>)"

if ([string]::IsNullOrWhiteSpace($SyncMethod)) {
    $SyncMethod = Read-Host -Prompt "Sync method [livesync|webdav] (default: webdav)"
    if ([string]::IsNullOrWhiteSpace($SyncMethod)) { $SyncMethod = "webdav" }
}

$SyncMethod = $SyncMethod.ToLower()
if ($SyncMethod -ne "livesync" -and $SyncMethod -ne "webdav") {
    Write-Err "SyncMethod must be 'livesync' or 'webdav', got: $SyncMethod"
}

# Strip trailing slash from server URL
$ServerUrl = $ServerUrl.TrimEnd("/")

# ---------------------------------------------------------------------------
# Locate / create the vault directory
# ---------------------------------------------------------------------------

$VaultBase   = Join-Path $HOME "Obsidian"
$VaultDir    = Join-Path $VaultBase $VaultName
$ObsidianDir = Join-Path $VaultDir ".obsidian"
$PluginsDir  = Join-Path $ObsidianDir "plugins"

if (Test-Path $VaultDir) {
    Write-Info "Vault directory already exists: $VaultDir"
} else {
    Write-Info "Creating vault directory: $VaultDir"
    New-Item -ItemType Directory -Path $VaultDir -Force | Out-Null
}

New-Item -ItemType Directory -Path $PluginsDir -Force | Out-Null

# ---------------------------------------------------------------------------
# Write plugin config
# ---------------------------------------------------------------------------

if ($SyncMethod -eq "livesync") {
    $PluginId  = "obsidian-livesync"
    $PluginDir = Join-Path $PluginsDir $PluginId
    $ConfigFile = Join-Path $PluginDir "data.json"

    New-Item -ItemType Directory -Path $PluginDir -Force | Out-Null

    $ShouldWrite = $false

    if (Test-Path $ConfigFile) {
        $Existing = Get-Content $ConfigFile -Raw -ErrorAction SilentlyContinue
        if ($Existing -match '"couchDB_URI"') {
            Write-Warn "Config already contains credentials: $ConfigFile"
            Write-Warn "Skipping write to avoid overwriting existing settings."
            Write-Warn "Delete the file and re-run to reset the configuration."
        } else {
            Write-Info "Config file exists but has no credentials — writing connection block."
            $ShouldWrite = $true
        }
    } else {
        $ShouldWrite = $true
    }

    if ($ShouldWrite) {
        Write-Info "Writing LiveSync config to: $ConfigFile"
        $ConfigJson = @"
{
  "couchDB_URI": "$ServerUrl/couchdb/$ProjectSlug",
  "couchDB_USER": "",
  "couchDB_PASSWORD": "$Token",
  "couchDB_DBNAME": "$ProjectSlug",
  "liveSync": true,
  "syncOnStart": true,
  "encrypt": true
}
"@
        Set-Content -Path $ConfigFile -Value $ConfigJson -Encoding UTF8
        Write-Ok "LiveSync config written."
    }

} else {
    # WebDAV / Remotely Save
    $PluginId   = "remotely-save"
    $PluginDir  = Join-Path $PluginsDir $PluginId
    $ConfigFile = Join-Path $PluginDir "data.json"

    New-Item -ItemType Directory -Path $PluginDir -Force | Out-Null

    $ShouldWrite = $false

    if (Test-Path $ConfigFile) {
        $Existing = Get-Content $ConfigFile -Raw -ErrorAction SilentlyContinue
        if ($Existing -match '"address"') {
            Write-Warn "Config already contains credentials: $ConfigFile"
            Write-Warn "Skipping write to avoid overwriting existing settings."
            Write-Warn "Delete the file and re-run to reset the configuration."
        } else {
            Write-Info "Config file exists but has no credentials — writing connection block."
            $ShouldWrite = $true
        }
    } else {
        $ShouldWrite = $true
    }

    if ($ShouldWrite) {
        Write-Info "Writing Remotely Save (WebDAV) config to: $ConfigFile"
        $ConfigJson = @"
{
  "s3": { "s3Endpoint": "", "s3Region": "", "s3AccessKeyID": "", "s3SecretAccessKey": "", "s3BucketName": "" },
  "webdav": {
    "address": "$ServerUrl/webdav/$ProjectSlug/",
    "username": "obsidian",
    "password": "$Token",
    "authType": "basic"
  },
  "dropbox": { "clientID": "", "clientSecret": "" },
  "onedrive": { "clientID": "", "clientSecret": "" },
  "serviceType": "webdav",
  "syncOnStartup": true,
  "autoRunEveryMilliseconds": 300000
}
"@
        Set-Content -Path $ConfigFile -Value $ConfigJson -Encoding UTF8
        Write-Ok "Remotely Save (WebDAV) config written."
    }
}

# ---------------------------------------------------------------------------
# Print next steps
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "========================================================"
Write-Host "  Next steps"
Write-Host "========================================================"
Write-Host ""
Write-Host "1. Open Obsidian."
Write-Host "   If this vault does not appear automatically, choose:"
Write-Host "   'Open folder as vault' -> $VaultDir"
Write-Host ""

if ($SyncMethod -eq "livesync") {
    Write-Host "2. Go to Settings -> Community plugins -> Browse"
    Write-Host "   Search for: Self-hosted LiveSync"
    Write-Host "   Install and Enable it."
    Write-Host ""
    Write-Host "3. Open Settings -> Self-hosted LiveSync -> Remote Database"
    Write-Host "   Verify the URI and credentials are pre-filled."
    Write-Host "   Fill in the Username field that was left blank."
    Write-Host "   URI: $ServerUrl/couchdb/$ProjectSlug"
    Write-Host ""
    Write-Host "4. Set up E2E encryption under the Encryption tab"
    Write-Host "   (use the shared passphrase your team agreed on)."
    Write-Host ""
    Write-Host "5. Click:"
    Write-Host "   - 'Initialize database' if this is the FIRST device for this project."
    Write-Host "   - 'Replicate' if another device has already been set up."
    Write-Host ""
    Write-Host "   WARNING: 'Initialize database' wipes the server DB."
    Write-Host "   Only run it once, on the very first device."
} else {
    Write-Host "2. Go to Settings -> Community plugins -> Browse"
    Write-Host "   Search for: Remotely Save"
    Write-Host "   Install and Enable it."
    Write-Host ""
    Write-Host "3. Open Settings -> Remotely Save"
    Write-Host "   Verify WebDAV address and credentials are pre-filled."
    Write-Host "   Address: $ServerUrl/webdav/$ProjectSlug/"
    Write-Host ""
    Write-Host "4. Click the cloud icon in the left sidebar (or"
    Write-Host "   Settings -> Remotely Save -> Run sync now) to trigger"
    Write-Host "   the first sync."
}

Write-Host ""
Write-Host "For full instructions: docs/setup-client.md"
Write-Host "========================================================"
