#Requires -Version 5.1
<#
.SYNOPSIS
  TB.0 · 停止本地演示进程（API/Web）；可选停 Docker
.PARAMETER AlsoInfra
  同时 docker compose stop 核心栈
#>
param(
  [switch]$AlsoInfra
)

$ErrorActionPreference = "Continue"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$PidDir = Join-Path $Root "deploy\dev\demo-pids"

function Stop-PidFile([string]$Name) {
  $f = Join-Path $PidDir "$Name.pid"
  if (-not (Test-Path $f)) {
    Write-Host "skip $Name (no pid file)"
    return
  }
  $id = Get-Content $f -ErrorAction SilentlyContinue
  if ($id) {
    Write-Host "stop $Name pid=$id"
    Stop-Process -Id ([int]$id) -Force -ErrorAction SilentlyContinue
    # also kill child trees loosely on Windows for npm
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
      Where-Object { $_.ParentProcessId -eq [int]$id } |
      ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  }
  Remove-Item $f -Force -ErrorAction SilentlyContinue
}

Write-Host "=== TB.0 stop-local ==="
Stop-PidFile "aos-api"
Stop-PidFile "aos-web"

if ($AlsoInfra) {
  Set-Location $Root
  Write-Host "docker compose stop core..."
  docker compose -f deploy/dev/docker-compose.yml stop `
    aos-dev-pg aos-dev-minio aos-dev-mysql aos-dev-llm-echo aos-dev-litellm aos-dev-ocr 2>$null
}

Write-Host "DONE"
exit 0
