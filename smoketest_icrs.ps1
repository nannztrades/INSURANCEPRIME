
<#
.SYNOPSIS
  End-to-end smoke test for ICRS on Windows/PowerShell 7.

.DESCRIPTION
  Waits for the API health endpoint, obtains CSRF + cookie session, logs in as an agent,
  (optionally) runs secure PDF validation, performs enhanced upload (ingest) for a STATEMENT,
  and fetches sample agent data (statements + uploads tracker). Saves key responses to ./out.

.PARAMETER BaseUrl           Default: http://localhost:8000
.PARAMETER AgentCode         Default: 9518
.PARAMETER Password          SecureString. If not provided, will use $env:ICRS_AGENT_PASSWORD (plain), or prompt.
.PARAMETER AgentName         Default: David Ferka
.PARAMETER MonthYear         Default: Jun 2025
.PARAMETER PdfPath           Default: D:\OneDrive\Desktop\Statement for June 2025 2.pdf
.PARAMETER HealthTimeoutSec  Seconds to wait for /health (default: 60)
.PARAMETER SkipValidate      If provided, skip secure PDF validation

.EXAMPLE
  # Interactive (prompts for password securely)
  .\smoketest_icrs.ps1 -BaseUrl http://localhost:8000 -AgentCode 9518 -MonthYear 'Jun 2025' -PdfPath 'D:\path\file.pdf'

.EXAMPLE
  # CI-friendly (password from env; avoid prompts)
  $env:ICRS_AGENT_PASSWORD = 'test123'
  .\smoketest_icrs.ps1 -BaseUrl http://localhost:8000 -AgentCode 9518 -MonthYear 'Jun 2025' -PdfPath 'D:\path\file.pdf' -SkipValidate

.EXAMPLE
  # Pass a SecureString explicitly
  $sec = ConvertTo-SecureString 'test123' -AsPlainText -Force
  .\smoketest_icrs.ps1 -Password $sec
#>

param(
  [string]$BaseUrl = 'http://localhost:8000',
  [string]$AgentCode = '9518',
  [SecureString]$Password,   # Secure by default; see acquisition below
  [string]$AgentName = 'David Ferka',
  [string]$MonthYear = 'Jun 2025',
  [string]$PdfPath = 'D:\OneDrive\Desktop\Statement for June 2025 2.pdf',
  [int]$HealthTimeoutSec = 60,
  [switch]$SkipValidate
)

$ErrorActionPreference = 'Stop'

function Write-Step {
  param([string]$Text, [ConsoleColor]$Color = [ConsoleColor]::Cyan)
  $old = $Host.UI.RawUI.ForegroundColor
  try { $Host.UI.RawUI.ForegroundColor = $Color; Write-Host "[STEP] $Text" }
  finally { $Host.UI.RawUI.ForegroundColor = $old }
}

function Write-Ok {
  param([string]$Text)
  $old = $Host.UI.RawUI.ForegroundColor
  try { $Host.UI.RawUI.ForegroundColor = 'Green'; Write-Host "[OK]   $Text" }
  finally { $Host.UI.RawUI.ForegroundColor = $old }
}

function Write-Fail {
  param([string]$Text)
  $old = $Host.UI.RawUI.ForegroundColor
  try { $Host.UI.RawUI.ForegroundColor = 'Red'; Write-Host "[FAIL] $Text" }
  finally { $Host.UI.RawUI.ForegroundColor = $old }
}

function Out-JsonFile {
  param([Parameter(Mandatory=$true)]$Object, [Parameter(Mandatory=$true)][string]$Path)
  $dir = Split-Path -Parent $Path
  if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  $Object | ConvertTo-Json -Depth 10 | Out-File -FilePath $Path -Encoding UTF8
}

# --- Ensure PowerShell 7 for -Form/-SkipHttpErrorCheck support ---
if ($PSVersionTable.PSVersion.Major -lt 7) {
  $pwsh = "C:\Program Files\PowerShell\7\pwsh.exe"
  if (Test-Path $pwsh) {
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
  } else {
    Write-Fail "PowerShell 7 is required to run this script."
    exit 1
  }
}

# 0) Pre-flight checks
Write-Step "Pre-flight checks"
if (-not (Get-Command Invoke-RestMethod -ErrorAction SilentlyContinue)) {
  Write-Fail "Invoke-RestMethod not found. PowerShell 7 required."
  exit 1
}
if (-not (Test-Path $PdfPath)) {
  Write-Fail "PDF not found: $PdfPath"
  exit 1
}
Write-Ok "PDF exists: $PdfPath"

# Acquire a SecureString password if not provided (env -> prompt)
if (-not $Password) {
  if ($env:ICRS_AGENT_PASSWORD) {
    $Password = ConvertTo-SecureString $env:ICRS_AGENT_PASSWORD -AsPlainText -Force
  } else {
    $Password = Read-Host -AsSecureString "Enter password for agent $AgentCode"
  }
}

# 1) Wait for /health
Write-Step "Waiting for $BaseUrl/health (timeout: ${HealthTimeoutSec}s)"
$deadline = (Get-Date).AddSeconds($HealthTimeoutSec)
$healthy = $false
while ((Get-Date) -lt $deadline) {
  try {
    $h = Invoke-RestMethod -Method GET -Uri ("{0}/health" -f $BaseUrl)
    if ($h.status -eq 'ok') { $healthy = $true; break }
  } catch { Start-Sleep -Milliseconds 500 }
  Start-Sleep -Milliseconds 500
}
if (-not $healthy) { Write-Fail "Service did not report healthy in time."; exit 2 }
Write-Ok "Service healthy"

# 2) CSRF
Write-Step "Obtaining CSRF token & cookie session"
$csrfResp = Invoke-RestMethod -Method GET -Uri ("{0}/api/auth/csrf" -f $BaseUrl) -SessionVariable websess
$csrf = $csrfResp.csrf_token
if (-not $csrf) { Write-Fail "No csrf_token returned"; exit 3 }
Write-Ok "CSRF token acquired"

# 3) Agent login (convert SecureString -> plain ONLY for the request, then clear)
Write-Step "Agent login for code '$AgentCode'"
$pwdPlain = [System.Net.NetworkCredential]::new('', $Password).Password
try {
  $loginHeaders = @{ 'Content-Type' = 'application/x-www-form-urlencoded'; 'X-CSRF-Token' = $csrf }
  $loginBody    = "agent_code=$([uri]::EscapeDataString($AgentCode))&password=$([uri]::EscapeDataString($pwdPlain))"
  $login = Invoke-RestMethod -Method POST -Uri ("{0}/api/auth/login/agent" -f $BaseUrl) -Headers $loginHeaders -Body $loginBody -WebSession $websess
} finally {
  # Minimize lifetime of the plain-text var
  $pwdPlain = $null
}
if (($login.status -ne 'OK') -and ($login.role -ne 'agent')) { Write-Fail "Login failed"; exit 4 }
Write-Ok ("Logged in as role '{0}' user_id={1}" -f $login.role, $login.user_id)
Out-JsonFile -Object $login -Path "out/login_response.json"

# 4) Optional secure validation
if (-not $SkipValidate.IsPresent) {
  Write-Step "Secure validating PDF (uploads-secure/statement)"
  $validateForm = @{ agent_code = $AgentCode; month_year = $MonthYear; file = Get-Item $PdfPath }
  $validate = Invoke-RestMethod -Method POST -Uri ("{0}/api/uploads-secure/statement" -f $BaseUrl) -Form $validateForm -WebSession $websess
  Write-Ok ("Validated: markers matched = {0}" -f $validate.markers_matched)
  Out-JsonFile -Object $validate -Path "out/validate_response.json"
} else {
  Write-Step "Skipping secure validation per -SkipValidate"
}

# 5) Enhanced upload & ingest (statement)
Write-Step "Enhanced upload & ingest (pdf-enhanced/upload/statement)"
$indoc = @{ agent_code = $AgentCode; agent_name = $AgentName; month_year = $MonthYear; file = Get-Item $PdfPath }
$ingest = Invoke-RestMethod -Method POST -Uri ("{0}/api/pdf-enhanced/upload/statement" -f $BaseUrl) -Form $indoc -WebSession $websess
$uploadId = $ingest.upload_id
if (-not $uploadId) { Write-Fail "No upload_id returned from ingest"; exit 5 }
Write-Ok ("Ingest complete: upload_id={0}, records={1}" -f $uploadId, $ingest.records_count)
Out-JsonFile -Object $ingest -Path "out/ingest_response.json"

# 6) Agent reads: statements + tracker
Write-Step "Fetching agent statements (sample)"
$mm = [uri]::EscapeDataString($MonthYear)
$stmts = Invoke-RestMethod -Method GET -Uri ("{0}/api/agent/statements?month_year={1}&limit=5" -f $BaseUrl, $mm) -WebSession $websess
$stmtsCount = $stmts.count
Write-Ok ("Statements returned (sample): count={0}" -f $stmtsCount)
Out-JsonFile -Object $stmts -Path "out/statements_sample.json"

Write-Step "Fetching uploads tracker"
# Keep your actual route: /api/agent/uploads/tracker?months_back=12
$trackerResp = Invoke-RestMethod -Method GET `
    -Uri ("{0}/api/agent/uploads/tracker?months_back=12" -f $BaseUrl) `
    -WebSession $websess `
    -SkipHttpErrorCheck `
    -StatusCodeVariable status

if ($status -ge 200 -and $status -lt 300) {
  Write-Ok "Uploads tracker fetched"
  Out-JsonFile -Object $trackerResp -Path "out/uploads_tracker.json"
  $monthRow = $null
  if ($trackerResp -and $trackerResp.items) {
    $monthRow = $trackerResp.items | Where-Object { $_.month_year -eq $MonthYear } | Select-Object -First 1
  }
}
else {
  Write-Host "[ERR]  /api/agent/uploads/tracker failed. Status:" $status
  if ($trackerResp -is [string]) {
    Write-Host "[ERR]  Body (raw):" $trackerResp
    try {
      $j = $trackerResp | ConvertFrom-Json
      Write-Host "[ERR]  Body (as JSON):" ($j | ConvertTo-Json -Depth 8)
      Out-JsonFile -Object $j -Path "out/uploads_tracker_error.json"
    } catch {
      # Keep raw if not JSON
      Set-Content -Path "out/uploads_tracker_error.txt" -Value $trackerResp -Encoding UTF8
    }
  } else {
    Write-Host "[ERR]  Body (obj):" ($trackerResp | ConvertTo-Json -Depth 8)
    Out-JsonFile -Object $trackerResp -Path "out/uploads_tracker_error.json"
  }

  # Fallback: capture the server's HTML error page to inspect stack trace
  try {
    $errPage = Invoke-WebRequest -Method GET `
      -Uri ("{0}/api/agent/uploads/tracker?months_back=12" -f $BaseUrl) `
      -WebSession $websess `
      -SkipHttpErrorCheck
    $htmlPath = "out/uploads_tracker_500.html"
    $errPage.Content | Out-File -FilePath $htmlPath -Encoding UTF8
    Write-Host "[ERR]  Saved server error page to $htmlPath"
  } catch {
    Write-Host "[ERR]  Could not fetch HTML error page:" $_.Exception.Message
  }

  throw "Uploads tracker failed with $status"
}

# 7) Summary
Write-Step "Summary"
$summary = [ordered]@{
  base_url                = $BaseUrl
  agent_code              = $AgentCode
  agent_name              = $AgentName
  month_year              = $MonthYear
  upload_id               = $uploadId
  records_ingested        = $ingest.records_count
  statements_sample_count = $stmtsCount
  tracker_row_for_month   = if ($monthRow) { $monthRow } else { $null }
  timestamp               = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
}
$summary | Format-List | Out-String | Write-Host
Out-JsonFile -Object $summary -Path "out/summary.json"

Write-Ok "Smoke test completed"
