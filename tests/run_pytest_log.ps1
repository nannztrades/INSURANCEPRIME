
<# run_pytest_log.ps1
   Runs pytest -q from the current directory and writes the full output
   to D:\PROJECT\INSURANCELOCAL\pytest_YYYYMMDD_HHMMSS.txt (same folder).
   Prints a short tail to the console and returns pytest's exit code. #>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Timestamped log file in the *current* directory
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$logPath = Join-Path -Path $PWD.Path -ChildPath ("pytest_{0}.txt" -f $ts)

Write-Host "Running tests... (full output will be written to $logPath)"

# Capture ALL output (stdout + stderr) directly into the file
# Using python -m pytest for consistency across environments
& python -m pytest -q > $logPath 2>&1
$exitCode = $LASTEXITCODE

# Show a concise tail so the terminal isn't flooded
Write-Host ""
Write-Host "──── Last 40 lines ───────────────────────────────────────────────" -ForegroundColor Cyan
if (Test-Path $logPath) {
    Get-Content -Path $logPath -Tail 40 | ForEach-Object { Write-Host $_ }
    Write-Host "──────────────────────────────────────────────────────────────────" -ForegroundColor Cyan
    Write-Host "Log saved to: $logPath"
} else {
    Write-Host "Log file not found (unexpected)." -ForegroundColor Yellow
}

# Exit using pytest's code (0=success, non-zero=failure)
exit $exitCode
