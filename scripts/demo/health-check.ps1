#Requires -Version 5.1
<#
.SYNOPSIS
  TB.0 · 本地演示健康检查
.PARAMETER InfraOnly
  只查 PG + MinIO（+ 可选 MySQL）
.PARAMETER RequireWeb
  Web :5173 必绿（默认：有则查，无则 WARN）
#>
param(
  [switch]$InfraOnly,
  [switch]$RequireWeb
)

$ErrorActionPreference = "Continue"
$fail = 0

function Test-Http([string]$Name, [string]$Url, [switch]$Required) {
  try {
    $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
    Write-Host ("OK   {0,-22} HTTP {1}  {2}" -f $Name, $r.StatusCode, $Url)
    return $true
  } catch {
    $msg = $_.Exception.Message
    if ($Required) {
      Write-Host ("FAIL {0,-22} {1}" -f $Name, $msg) -ForegroundColor Red
      $script:fail++
    } else {
      Write-Host ("WARN {0,-22} {1}" -f $Name, $msg) -ForegroundColor Yellow
    }
    return $false
  }
}

Write-Host "=== TB.0 health-check ==="

# PG
docker exec aos-dev-pg pg_isready -U aos_app -d aos_meta 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
  Write-Host ("OK   {0,-22} accepting" -f "PostgreSQL :5433")
} else {
  Write-Host ("FAIL {0,-22} not ready" -f "PostgreSQL :5433") -ForegroundColor Red
  $fail++
}

Test-Http "MinIO :9000" "http://127.0.0.1:9000/minio/health/live" -Required | Out-Null

if (-not $InfraOnly) {
  Test-Http "aos-api /v1/health" "http://127.0.0.1:8080/v1/health" -Required | Out-Null
  # optional sidecars — warn only
  Test-Http "LiteLLM :4001" "http://127.0.0.1:4001/health/liveliness" | Out-Null
  Test-Http "OCR :8082" "http://127.0.0.1:8082/health" | Out-Null
  Test-Http "Analytics :8084" "http://127.0.0.1:8084/health" | Out-Null
  if ($RequireWeb) {
    Test-Http "web :5173" "http://127.0.0.1:5173/" -Required | Out-Null
  } else {
    Test-Http "web :5173" "http://127.0.0.1:5173/" | Out-Null
  }
}

Write-Host ""
if ($fail -eq 0) {
  Write-Host "RESULT: DEMO HEALTH OK" -ForegroundColor Green
  exit 0
}
Write-Host "RESULT: DEMO HEALTH FAIL ($fail)" -ForegroundColor Red
exit 1
