
<# 
  cleanup_insurance_local.ps1
  Purpose: Remove non-system artifacts from the local project folder.
  Safe defaults: Dry-run first, detailed output, preserves source/tests/deploy files.

  Usage:
    # 1) See what would be deleted (no changes)
    .\cleanup_insurance_local.ps1 -Root "D:\PROJECT\INSURANCELOCAL" -DryRun

    # 2) Perform actual deletion (asks for confirmation)
    .\cleanup_insurance_local.ps1 -Root "D:\PROJECT\INSURANCELOCAL"

  Optional flags:
    -SkipConfirm  # delete without confirmation prompt (CI usage)
#>

param(
  [Parameter(Mandatory=$true)]
  [string]$Root,

  [switch]$DryRun,

  [switch]$SkipConfirm
)

function Resolve-PathSafe {
  param([string]$p)
  try { return (Resolve-Path -LiteralPath $p -ErrorAction Stop).Path }
  catch { return $null }
}

Write-Host "=== Cleanup: InsuranceLocal ===" -ForegroundColor Cyan
Write-Host "Root: $Root" -ForegroundColor Cyan
if ($DryRun) { Write-Host "Mode: DRY-RUN (no changes will be made)" -ForegroundColor Yellow }

# ---------------------------
# Define targets to remove
# ---------------------------
$foldersToRemove = @(
  ".pytest_cache",
  ".vscode",
  "data\incoming",
  "data\failed",
  "data\processed",
  "data\previews",
  "logs",
  "exports",
  "reports",
  "backup"
)

$filesToRemove = @(
  "list_routes.py",
  "project_tree.txt",
  "tmp_expected.py",
  "upgrade_py39_log.txt",
  "endpoints.csv",
  "if i ever want to hard delete agent in dbeaver.txt",
  "desktop.ini",
  "123"
)

# ---------------------------
# Safety: whitelist to preserve
# ---------------------------
$protectedPaths = @(
  "src",
  "tests",
  "requirements.txt",
  "Dockerfile",
  "alembic.ini",
  "migrations",
  ".env.example",
  "pytest.ini",
  ".gitignore",
  "railway.toml",
  "pyrightconfig.json",
  ".env"
)

# Convert to absolute paths
$absFolders = $foldersToRemove | ForEach-Object { Join-Path -Path $Root -ChildPath $_ }
$absFiles   = $filesToRemove   | ForEach-Object { Join-Path -Path $Root -ChildPath $_ }
$absProtect = $protectedPaths  | ForEach-Object { Join-Path -Path $Root -ChildPath $_ }

# Quick sanity: do not proceed if $Root doesn't look right
if (-not (Test-Path -LiteralPath $Root)) {
  Write-Host "ERROR: Root path does not exist: $Root" -ForegroundColor Red
  exit 2
}

# Warn if any target collides with protected paths
foreach ($p in $absProtect) {
  foreach ($f in $absFolders + $absFiles) {
    if ((Resolve-PathSafe $p) -and (Resolve-PathSafe $f) -and ((Resolve-PathSafe $p) -eq (Resolve-PathSafe $f))) {
      Write-Host "ERROR: Target '$f' is protected. Aborting." -ForegroundColor Red
      exit 3
    }
  }
}

# Collect existing targets
$existingFolders = @()
$existingFiles   = @()

foreach ($d in $absFolders) { if (Test-Path -LiteralPath $d) { $existingFolders += $d } }
foreach ($f in $absFiles)   { if (Test-Path -LiteralPath $f) { $existingFiles   += $f } }

Write-Host "Found $($existingFolders.Count) folders and $($existingFiles.Count) files to remove." -ForegroundColor Green

# Show plan
Write-Host "`n--- Folders to remove ---" -ForegroundColor Gray
$existingFolders | ForEach-Object { Write-Host "  - $_" }
Write-Host "`n--- Files to remove ---" -ForegroundColor Gray
$existingFiles   | ForEach-Object { Write-Host "  - $_" }

if ($DryRun) {
  Write-Host "`nDRY-RUN complete. No changes made." -ForegroundColor Yellow
  exit 0
}

# Confirm
if (-not $SkipConfirm) {
  $answer = Read-Host "`nProceed to DELETE these items? Type 'yes' to confirm"
  if ($answer -ne "yes") {
    Write-Host "Cancelled by user." -ForegroundColor Yellow
    exit 0
  }
}

# ---------------------------
# Delete phase
# ---------------------------
$deleted = 0
$failed  = 0

foreach ($d in $existingFolders) {
  try {
    # Extra safeguard: only remove top-level targets (no src/tests/etc.)
    if ($absProtect -contains $d) {
      Write-Host "SKIP (protected folder): $d" -ForegroundColor Yellow
      continue
    }
    Remove-Item -LiteralPath $d -Recurse -Force -ErrorAction Stop
    Write-Host "Deleted folder: $d" -ForegroundColor Green
    $deleted++
  } catch {
    Write-Host "FAILED to delete folder: $d  -> $($_.Exception.Message)" -ForegroundColor Red
    $failed++
  }
}

foreach ($f in $existingFiles) {
  try {
    if ($absProtect -contains $f) {
      Write-Host "SKIP (protected file): $f" -ForegroundColor Yellow
      continue
    }
    Remove-Item -LiteralPath $f -Force -ErrorAction Stop
    Write-Host "Deleted file: $f" -ForegroundColor Green
    $deleted++
  } catch {
    Write-Host "FAILED to delete file: $f  -> $($_.Exception.Message)" -ForegroundColor Red
    $failed++
  }
}

Write-Host "`nCleanup complete. Deleted: $deleted, Failed: $failed" -ForegroundColor Cyan

# Optional: print a short reminder
Write-Host "`nNext steps:" -ForegroundColor Gray
Write-Host "  1) Verify the tree:" -ForegroundColor Gray
Write-Host "     python D:\PROJECT\INSURANCELOCAL\src\cli\show_tree_detailed.py" -ForegroundColor Gray
Write-Host "  2) Re-push to GitHub and proceed to Railway setup." -ForegroundColor Gray
