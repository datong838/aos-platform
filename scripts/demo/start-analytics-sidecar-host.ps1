# Start shaped analytics-runtime on the host (no Docker) — TA.1 / doc 110.
# Usage: powershell -File scripts/demo/start-analytics-sidecar-host.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$AppDir = Join-Path $Root "deploy\dev\analytics-runtime"
if (-not (Test-Path (Join-Path $AppDir "app.py"))) {
  throw "analytics-runtime app.py not found: $AppDir"
}
Write-Host "analytics-runtime shaped → http://127.0.0.1:8084/health"
Write-Host "Set AOS_ANALYTICS_URL=http://127.0.0.1:8084 before starting aos-api"
Set-Location $AppDir
python -m uvicorn app:app --host 127.0.0.1 --port 8084
