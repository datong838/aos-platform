#Requires -Version 5.1
<#
.SYNOPSIS
  TB.0 · 本地演示一键启动（业务平台优先 · Apollo 运维后置）
.DESCRIPTION
  1) docker compose 拉起 PG/MinIO/MySQL/LLM/OCR（不含 oidc/openfga profile）
  2) 后台启动 aos-api :8080 与 web :5173（可用 -InfraOnly 跳过）
  3) 跑 health-check
.PARAMETER InfraOnly
  只起 Docker 前置，不起 API/Web
.PARAMETER SkipInstall
  跳过 pip install -e . / npm install
.PARAMETER SkipWeb
  不起 Web
.EXAMPLE
  powershell -File scripts/demo/start-local.ps1
#>
param(
  [switch]$InfraOnly,
  [switch]$SkipInstall,
  [switch]$SkipWeb
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root
$LogDir = Join-Path $Root "deploy\dev"
$PidDir = Join-Path $LogDir "demo-pids"
New-Item -ItemType Directory -Force -Path $PidDir | Out-Null

function Write-Step([string]$Msg) { Write-Host ""; Write-Host "=== $Msg ===" -ForegroundColor Cyan }

Write-Step "TB.0 start-local · root=$Root"

# --- 1) Infra ---
Write-Step "Docker compose up (core stack)"
$compose = "deploy/dev/docker-compose.yml"
if (-not (Test-Path $compose)) { throw "missing $compose" }
docker compose -f $compose up -d aos-dev-pg aos-dev-minio aos-dev-minio-init aos-dev-mysql aos-dev-llm-echo aos-dev-litellm aos-dev-ocr
if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }

Write-Step "Wait PostgreSQL"
$deadline = (Get-Date).AddSeconds(90)
do {
  docker exec aos-dev-pg pg_isready -U aos_app -d aos_meta 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) { break }
  Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)
docker exec aos-dev-pg pg_isready -U aos_app -d aos_meta 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL not ready on :5433" }
Write-Host "PostgreSQL ONLINE"

if ($InfraOnly) {
  Write-Step "InfraOnly — run health infra probes"
  & (Join-Path $PSScriptRoot "health-check.ps1") -InfraOnly
  exit $LASTEXITCODE
}

# --- 2) API ---
Write-Step "aos-api :8080"
$apiDir = Join-Path $Root "services\aos-api"
if (-not $SkipInstall) {
  Push-Location $apiDir
  try {
    python -m pip install -e . -q
  } finally {
    Pop-Location
  }
}

# stop previous demo api if pid file exists
$apiPidFile = Join-Path $PidDir "aos-api.pid"
if (Test-Path $apiPidFile) {
  $old = Get-Content $apiPidFile -ErrorAction SilentlyContinue
  if ($old) {
    Stop-Process -Id ([int]$old) -Force -ErrorAction SilentlyContinue
  }
  Remove-Item $apiPidFile -Force -ErrorAction SilentlyContinue
}

$apiOut = Join-Path $LogDir "aos-api.out.log"
$apiErr = Join-Path $LogDir "aos-api.err.log"
$env:AOS_LOG_LEVEL = "debug"
$env:AOS_LOG_FORMAT = "json"
$env:AOS_AUTH_ALLOW_DEV = "1"
$pApi = Start-Process -FilePath "python" `
  -ArgumentList @("-m", "uvicorn", "aos_api.main:app", "--host", "127.0.0.1", "--port", "8080") `
  -WorkingDirectory $apiDir `
  -RedirectStandardOutput $apiOut `
  -RedirectStandardError $apiErr `
  -WindowStyle Hidden `
  -PassThru
Set-Content -Path $apiPidFile -Value $pApi.Id -Encoding ascii
Write-Host "aos-api pid=$($pApi.Id) log=$apiOut"

# wait health
$apiOk = $false
for ($i = 0; $i -lt 45; $i++) {
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8080/v1/health" -UseBasicParsing -TimeoutSec 2
    if ($r.StatusCode -eq 200) { $apiOk = $true; break }
  } catch { Start-Sleep -Seconds 1 }
}
if (-not $apiOk) {
  Write-Host "aos-api failed to become healthy — tail err log:" -ForegroundColor Red
  if (Test-Path $apiErr) { Get-Content $apiErr -Tail 40 }
  throw "aos-api /v1/health not 200"
}
Write-Host "aos-api ONLINE"

# --- 3) Web ---
if (-not $SkipWeb) {
  Write-Step "web :5173"
  $webDir = Join-Path $Root "apps\web"
  if (-not $SkipInstall) {
    Push-Location $webDir
    try {
      if (-not (Test-Path "node_modules")) { npm install }
    } finally {
      Pop-Location
    }
  }
  $webPidFile = Join-Path $PidDir "aos-web.pid"
  if (Test-Path $webPidFile) {
    $oldW = Get-Content $webPidFile -ErrorAction SilentlyContinue
    if ($oldW) { Stop-Process -Id ([int]$oldW) -Force -ErrorAction SilentlyContinue }
    Remove-Item $webPidFile -Force -ErrorAction SilentlyContinue
  }
  $webOut = Join-Path $LogDir "aos-web.out.log"
  $webErr = Join-Path $LogDir "aos-web.err.log"
  $npmCmd = (Get-Command npm.cmd -ErrorAction SilentlyContinue)
  if (-not $npmCmd) { $npmCmd = Get-Command npm }
  $pWeb = Start-Process -FilePath $npmCmd.Source `
    -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "5173") `
    -WorkingDirectory $webDir `
    -RedirectStandardOutput $webOut `
    -RedirectStandardError $webErr `
    -WindowStyle Hidden `
    -PassThru
  Set-Content -Path $webPidFile -Value $pWeb.Id -Encoding ascii
  Write-Host "web pid=$($pWeb.Id) log=$webOut"

  $webOk = $false
  for ($i = 0; $i -lt 60; $i++) {
    try {
      $r = Invoke-WebRequest -Uri "http://127.0.0.1:5173/" -UseBasicParsing -TimeoutSec 2
      if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { $webOk = $true; break }
    } catch { Start-Sleep -Seconds 1 }
  }
  if (-not $webOk) {
    Write-Host "web not ready yet — check $webErr (continuing; health-check will report)" -ForegroundColor Yellow
  } else {
    Write-Host "web ONLINE"
  }
}

Write-Step "health-check"
& (Join-Path $PSScriptRoot "health-check.ps1")
$code = $LASTEXITCODE

Write-Host ""
Write-Host "Demo URLs:" -ForegroundColor Green
Write-Host "  API   http://127.0.0.1:8080/v1/health"
Write-Host "  Web   http://127.0.0.1:5173/"
Write-Host "  Auth  Bearer dev  (AOS_AUTH_ALLOW_DEV=1)"
Write-Host "Stop:   powershell -File scripts/demo/stop-local.ps1"
exit $code
