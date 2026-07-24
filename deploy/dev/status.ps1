#Requires -Version 5.1
# Dev infra online check — PG + MinIO (aos-platform/deploy/dev)
# Usage: powershell -File deploy/dev/status.ps1
$ErrorActionPreference = "Continue"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not (Test-Path (Join-Path $Root "deploy\dev\docker-compose.yml"))) {
  $Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
}
Set-Location $Root

Write-Host "=== compose ps ==="
docker compose -f deploy/dev/docker-compose.yml ps -a

function Test-Http([string]$Url) {
  try {
    $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
    return "ONLINE HTTP $($r.StatusCode)"
  } catch {
    return "OFFLINE ($($_.Exception.Message))"
  }
}

Write-Host ""
Write-Host "=== probes ==="
$pg = docker exec aos-dev-pg pg_isready -U aos_app -d aos_meta 2>&1
if ($LASTEXITCODE -eq 0) { Write-Host "PostgreSQL :5433  ONLINE  $pg" } else { Write-Host "PostgreSQL :5433  OFFLINE  $pg" }

$minioLive = Test-Http "http://127.0.0.1:9000/minio/health/live"
Write-Host "MinIO API  :9000  $minioLive"
$minioConsole = Test-Http "http://127.0.0.1:9001"
Write-Host "MinIO UI   :9001  $minioConsole"

$ok = ($LASTEXITCODE -eq 0) -or ($pg -match "accepting")
# re-check pg explicitly
docker exec aos-dev-pg pg_isready -U aos_app -d aos_meta 2>$null | Out-Null
$pgOk = ($LASTEXITCODE -eq 0)
$minioOk = $minioLive -match "ONLINE"
if ($pgOk -and $minioOk) {
  Write-Host ""
  Write-Host "RESULT: Dev prereq ONLINE (PG + MinIO)"
  exit 0
}
Write-Host ""
Write-Host "RESULT: Dev prereq NOT fully online"
exit 1
