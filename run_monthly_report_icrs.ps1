
#Requires -Version 7.0
<#
ICRS – Agent Monthly Report Runner (Local Dev)
- Logs in as agent (CSRF-safe), generates monthly report, downloads PDF & CSV,
  fetches summary, missing, tracker row, pay-date disparities, then prints a recap.

Defaults:
  -BaseUrl   http://localhost:8000
  -AgentCode 9518
  -MonthYear "Jun 2025"
  -OutDir    "D:\PROJECT\INSURANCELOCAL\reports"
#>

param(
  [string]$BaseUrl   = "http://localhost:8000",
  [string]$AgentCode = "9518",
  [string]$MonthYear = "Jun 2025",
  [string]$OutDir    = "D:\PROJECT\INSURANCELOCAL\reports"
)

$ErrorActionPreference = 'Stop'
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12

function Write-Step($msg) { Write-Host "[STEP] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "[ERR]  $msg" -ForegroundColor Red }

# Ensure output directory exists
if (-not (Test-Path -LiteralPath $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

# Create a reusable web session to persist cookies
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

function Get-CsrfToken {
  $url = "$BaseUrl/api/auth/csrf"
  $resp = Invoke-RestMethod -Method GET -Uri $url -WebSession $session
  if (-not $resp.csrf_token) { throw "CSRF token not returned." }
  return $resp.csrf_token
}

function Login-Agent {
  param([string]$AgentCode, [securestring]$SecurePassword)
  $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
             [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePassword))
  try {
    $csrf = Get-CsrfToken
    $body = @{
      agent_code = $AgentCode
      password   = $plain
    }
    $headers = @{ "X-CSRF-Token" = $csrf }
    $url = "$BaseUrl/api/auth/login/agent"
    $resp = Invoke-RestMethod -Method POST -Uri $url `
              -Headers $headers `
              -ContentType "application/x-www-form-urlencoded" `
              -Body $body -WebSession $session
    if ($resp.status -ne "OK" -or $resp.role -ne "agent") {
      throw "Login failed (unexpected payload)."
    }
    return $resp
  }
  finally {
    if ($plain) { [System.Array]::Clear([char[]]$plain, 0, $plain.Length) }
  }
}

function Me {
  $url = "$BaseUrl/api/auth/me"
  try {
    $resp = Invoke-RestMethod -Method GET -Uri $url -WebSession $session
    return $resp
  } catch {
    return $null
  }
}

function Generate-MonthlyReport {
  param(
    [string]$AgentCode, [string]$MonthYear, [string]$OutDir, [int]$UserId = 0
  )
  $body = @{
    agent_code = $AgentCode
    month_year = $MonthYear
    out        = $OutDir
    user_id    = $UserId
    skip_pdf   = $false
    dry_run    = $false
  }
  $url = "$BaseUrl/api/agent/reports/generate"
  $resp = Invoke-RestMethod -Method POST -Uri $url `
            -ContentType "application/x-www-form-urlencoded" `
            -Body $body -WebSession $session
  return $resp
}

function Get-ReportsList {
  param([string]$AgentCode, [string]$MonthYear)
  $url = "$BaseUrl/api/agent/reports?agent_code=$([uri]::EscapeDataString($AgentCode))&month_year=$([uri]::EscapeDataString($MonthYear))"
  $resp = Invoke-RestMethod -Method GET -Uri $url -WebSession $session
  return $resp
}

function Download-ReportPdf {
  param([int]$ReportId, [string]$TargetPath)
  $url = "$BaseUrl/api/agent/reports/download/$ReportId"
  Invoke-WebRequest -Method GET -Uri $url -WebSession $session -OutFile $TargetPath | Out-Null
  return $TargetPath
}

function Export-ReportCsv {
  param([string]$AgentCode, [string]$MonthYear, [string]$TargetPath)
  $url = "$BaseUrl/api/agent/reports/export-csv?agent_code=$([uri]::EscapeDataString($AgentCode))&month_year=$([uri]::EscapeDataString($MonthYear))"
  Invoke-WebRequest -Method GET -Uri $url -WebSession $session -OutFile $TargetPath | Out-Null
  return $TargetPath
}

function Get-AgentSummary {
  param([string]$AgentCode, [string]$MonthYear)
  $url = "$BaseUrl/api/agent/summary?agent_code=$([uri]::EscapeDataString($AgentCode))&month_year=$([uri]::EscapeDataString($MonthYear))"
  return (Invoke-RestMethod -Method GET -Uri $url -WebSession $session)
}

function Get-UploadsTrackerRow {
  param([string]$AgentCode, [string]$MonthYear)
  $url = "$BaseUrl/api/agent/uploads/tracker?months_back=60"
  $resp = Invoke-RestMethod -Method GET -Uri $url -WebSession $session
  $row = $null
  if ($resp.items) {
    $row = $resp.items | Where-Object { $_.month_year -eq $MonthYear } | Select-Object -First 1
  }
  return $row
}

function Get-MissingPolicies {
  param([string]$MonthYear)
  $url = "$BaseUrl/api/agent/missing?month_year=$([uri]::EscapeDataString($MonthYear))"
  return (Invoke-RestMethod -Method GET -Uri $url -WebSession $session)
}

function Get-PayDateDisparities {
  param([string]$AgentCode, [string]$MonthYear)
  $url = "$BaseUrl/api/disparities/pay-date?agent_code=$([uri]::EscapeDataString($AgentCode))&month_year=$([uri]::EscapeDataString($MonthYear))"
  return (Invoke-RestMethod -Method GET -Uri $url -WebSession $session)
}

# ────────────────────────────────────────────────────────────────────────────────
# RUN
# ────────────────────────────────────────────────────────────────────────────────

Write-Step "Pre-flight checks"
$health = Invoke-RestMethod -Method GET -Uri "$BaseUrl/health" -ErrorAction SilentlyContinue
if (-not $health -or $health.status -ne "ok") {
  Write-Fail "Service not healthy at $BaseUrl"
  exit 1
}
Write-Ok "Service healthy"

# Secure password prompt
$securePwd = Read-Host -AsSecureString -Prompt "Enter password for agent $AgentCode"

Write-Step "Agent login (agent_code='$AgentCode')"
$login = Login-Agent -AgentCode $AgentCode -SecurePassword $securePwd
Write-Ok "Logged in as role '$($login.role)' user_id=$($login.user_id)"

# Who am I?
$me = Me
$userId = 0
if ($me -and $me.identity -and $me.identity.user_id) { $userId = [int]$me.identity.user_id }

Write-Step "Generating monthly report (Agent=$AgentCode, Month=$MonthYear)"
$gen = Generate-MonthlyReport -AgentCode $AgentCode -MonthYear $MonthYear -OutDir $OutDir -UserId $userId
if ($gen.status -ne "SUCCESS") { Write-Fail "Report generation did not return SUCCESS"; exit 1 }
Write-Ok "Monthly report generated; expected_rows_inserted=$($gen.expected_rows_inserted)"

Write-Step "Fetching report list for month"
$repList = Get-ReportsList -AgentCode $AgentCode -MonthYear $MonthYear
if (-not $repList.items -or $repList.items.Count -lt 1) {
  Write-Fail "No report rows found for $MonthYear"
  exit 1
}
# Select newest report_id
$latest = ($repList.items | Sort-Object { $_.report_id } -Descending | Select-Object -First 1)
$reportId = [int]$latest.report_id
Write-Ok "Latest report_id=$reportId"

# Targets
$periodKey = ($MonthYear -replace '^COM_', '') -replace ' ', '-'
$pdfPath = Join-Path $OutDir ("ICRS_{0}_{1}.pdf" -f $AgentCode, $periodKey)
$csvPath = Join-Path $OutDir ("ICRS_{0}_{1}.csv" -f $AgentCode, $periodKey)

Write-Step "Downloading PDF"
$finalPdf = Download-ReportPdf -ReportId $reportId -TargetPath $pdfPath
Write-Ok "PDF saved: $finalPdf"

Write-Step "Exporting CSV"
$finalCsv = Export-ReportCsv -AgentCode $AgentCode -MonthYear $MonthYear -TargetPath $csvPath
Write-Ok "CSV saved: $finalCsv"

Write-Step "Fetching analytics (summary, missing, tracker, pay-date disparities)"
$summary   = Get-AgentSummary -AgentCode $AgentCode -MonthYear $MonthYear
$missing   = Get-MissingPolicies -MonthYear $MonthYear
$tracker   = Get-UploadsTrackerRow -AgentCode $AgentCode -MonthYear $MonthYear
$dispar    = Get-PayDateDisparities -AgentCode $AgentCode -MonthYear $MonthYear

# Build a compact recap
$missingCount = 0
if ($missing.items) { $missingCount = [int]$missing.items.Count }

$disparCount  = 0
$futureCount  = 0
$pastCount    = 0
$totalPremAffect = 0.0
if ($dispar.summary) {
  $disparCount      = [int]$dispar.summary.total_disparities
  $futureCount      = [int]$dispar.summary.future_dated_count
  $pastCount        = [int]$dispar.summary.past_dated_count
  $totalPremAffect  = [double]$dispar.summary.total_premium_affected
}

Write-Host ""
Write-Step "Summary"
$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$recap = [ordered]@{
  base_url                   = $BaseUrl
  agent_code                 = $AgentCode
  month_year                 = $MonthYear
  pdf_saved                  = $finalPdf
  csv_saved                  = $finalCsv
  active_policies_total      = $summary.active_policies_total
  policy_type_counts         = ($summary.policy_type_counts | ConvertTo-Json -Compress)
  missing_policies_count     = $missingCount
  pay_date_disparities_total = $disparCount
  pay_date_future_count      = $futureCount
  pay_date_past_count        = $pastCount
  premium_affected_sum       = ("{0:N2}" -f $totalPremAffect)
  tracker_row_for_month      = ($tracker | ConvertTo-Json -Compress)
  timestamp                  = $ts
}

$recap.GetEnumerator() | ForEach-Object {
  "{0,-30}: {1}" -f $_.Key, $_.Value
} | Write-Host

Write-Ok "Agent monthly report flow completed."
