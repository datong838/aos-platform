#Requires -Version 5.1
<#
  Probe Dev OpenFGA sidecar — schemes 58/61
  Skip (exit 0) when unreachable.

  Usage (from aos-platform):
    .\scripts\ci\probe-openfga.ps1
#>
param(
    [string]$Base = "http://127.0.0.1:8085",
    [string]$ApiBase = "http://127.0.0.1:8080",
    [string]$StoreId = "",
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
)

$ErrorActionPreference = "Stop"
$envFile = Join-Path $Root "deploy\dev\openfga-store.env"
if (-not $StoreId -and (Test-Path $envFile)) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^AOS_OPENFGA_STORE_ID=(.+)$') { $StoreId = $Matches[1].Trim() }
        if ($_ -match '^AOS_OPENFGA_API_URL=(.+)$') { $Base = $Matches[1].Trim() }
    }
}

function Test-Url([string]$Url) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        return $r.StatusCode -ge 200 -and $r.StatusCode -lt 500
    } catch {
        return $false
    }
}

Write-Host "probe OpenFGA: $Base"
if (-not (Test-Url "$Base/healthz") -and -not (Test-Url "$Base/stores")) {
    Write-Host "SKIP: OpenFGA not up. Start with:"
    Write-Host "  docker compose -f deploy/dev/docker-compose.yml --profile openfga up -d"
    Write-Host "  .\scripts\ci\bootstrap-openfga.ps1"
    exit 0
}

if (-not $StoreId) {
    Write-Warning "No store id. Run bootstrap-openfga.ps1 first (IdP-side OK)."
    exit 0
}

$body = @{
    tuple_key = @{
        user     = "user:secret-user"
        relation = "viewer"
        object   = "object:WorkOrder:wo-fga-demo"
    }
} | ConvertTo-Json -Depth 5 -Compress
$check = Invoke-RestMethod -Method Post -Uri "$Base/stores/$StoreId/check" `
    -ContentType "application/json" -Body $body -TimeoutSec 10
if (-not $check.allowed) {
    Write-Error "OpenFGA check denied for seed tuple"
    exit 1
}
Write-Host "OK OpenFGA check viewer allowed"

$orgBody = @{
    tuple_key = @{
        user     = "user:secret-user"
        relation = "member"
        object   = "organization:dev-org"
    }
} | ConvertTo-Json -Depth 5 -Compress
try {
    $orgCheck = Invoke-RestMethod -Method Post -Uri "$Base/stores/$StoreId/check" `
        -ContentType "application/json" -Body $orgBody -TimeoutSec 10
    if ($orgCheck.allowed) {
        Write-Host "OK OpenFGA org member (scheme 61)"
    } else {
        Write-Warning "org member denied — re-run bootstrap-openfga.ps1 for aos-prod-v1 model"
    }
} catch {
    Write-Warning "org member check skipped (old store?): $_"
}

try {
    $st = Invoke-RestMethod -Uri "$ApiBase/v1/authz/status" -Headers @{
        Authorization = "Bearer dev"
        "X-Org-Id" = "dev-org"
        "X-Project-Id" = "dev-project"
    } -TimeoutSec 5
    Write-Host "OK /v1/authz/status mode=$($st.mode) reachable=$($st.reachable) model=$($st.modelVersion)"
} catch {
    Write-Warning "aos-api /v1/authz/status not reachable (set AOS_OPENFGA_* and restart). Sidecar OK."
}

Write-Host "probe-openfga OK"
exit 0
