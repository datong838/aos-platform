#Requires -Version 5.1
<#
  Bootstrap Dev OpenFGA — schemes 58/61
  Creates store + authorization model (aos-prod-v1) + seed tuples.
  Writes deploy/dev/openfga-store.env (gitignored).

  Usage (from aos-platform):
    docker compose -f deploy/dev/docker-compose.yml --profile openfga up -d
    .\scripts\ci\bootstrap-openfga.ps1
#>
param(
    [string]$Base = "http://127.0.0.1:8085",
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
)

$ErrorActionPreference = "Stop"
$modelPath = Join-Path $Root "deploy\dev\openfga\model.json"
$outEnv = Join-Path $Root "deploy\dev\openfga-store.env"

function Invoke-Json([string]$Method, [string]$Url, $Body = $null) {
    $params = @{
        Method      = $Method
        Uri         = $Url
        ContentType = "application/json"
        TimeoutSec  = 15
    }
    if ($null -ne $Body) {
        $params.Body = ($Body | ConvertTo-Json -Depth 20 -Compress)
    }
    return Invoke-RestMethod @params
}

Write-Host "bootstrap OpenFGA at $Base"
try {
    $null = Invoke-WebRequest -Uri "$Base/healthz" -UseBasicParsing -TimeoutSec 5
} catch {
    try {
        $null = Invoke-RestMethod -Uri "$Base/stores" -TimeoutSec 5
    } catch {
        Write-Host "SKIP: OpenFGA not reachable at $Base"
        Write-Host "  docker compose -f deploy/dev/docker-compose.yml --profile openfga up -d"
        exit 0
    }
}

$store = Invoke-Json POST "$Base/stores" @{ name = "aos-dev" }
$storeId = $store.id
if (-not $storeId) { Write-Error "create store failed"; exit 1 }
Write-Host "OK store id=$storeId"

$model = Get-Content -Raw $modelPath | ConvertFrom-Json
$written = Invoke-Json POST "$Base/stores/$storeId/authorization-models" $model
Write-Host "OK authorization model $($written.authorization_model_id)"

$tupleBody = @{
    writes = @{
        tuple_keys = @(
            @{
                user     = "user:secret-user"
                relation = "viewer"
                object   = "object:WorkOrder:wo-fga-demo"
            },
            @{
                user     = "user:secret-user"
                relation = "member"
                object   = "organization:dev-org"
            },
            @{
                user     = "organization:dev-org"
                relation = "parent"
                object   = "project:dev-project"
            },
            @{
                user     = "user:secret-user"
                relation = "bearer"
                object   = "marking:restricted"
            }
        )
    }
}
$null = Invoke-Json POST "$Base/stores/$storeId/write" $tupleBody
Write-Host "OK seed tuples (viewer · org member · project parent · marking bearer)"

$check = Invoke-Json POST "$Base/stores/$storeId/check" @{
    tuple_key = @{
        user     = "user:secret-user"
        relation = "viewer"
        object   = "object:WorkOrder:wo-fga-demo"
    }
}
if (-not $check.allowed) {
    Write-Error "seed check not allowed"
    exit 1
}
Write-Host "OK check viewer allowed=true"

$checkOrg = Invoke-Json POST "$Base/stores/$storeId/check" @{
    tuple_key = @{
        user     = "user:secret-user"
        relation = "member"
        object   = "organization:dev-org"
    }
}
if (-not $checkOrg.allowed) {
    Write-Error "org member check not allowed"
    exit 1
}
Write-Host "OK check org member allowed=true"

# project member via parent (computed)
$checkProj = Invoke-Json POST "$Base/stores/$storeId/check" @{
    tuple_key = @{
        user     = "user:secret-user"
        relation = "member"
        object   = "project:dev-project"
    }
}
if (-not $checkProj.allowed) {
    Write-Error "project member-from-parent check not allowed"
    exit 1
}
Write-Host "OK check project member (from parent) allowed=true"

@(
    "AOS_OPENFGA_API_URL=$Base"
    "AOS_OPENFGA_STORE_ID=$storeId"
    "AOS_OPENFGA_STRICT=0"
) | Set-Content -Path $outEnv -Encoding UTF8
Write-Host "Wrote $outEnv"
Write-Host "HINT: merge into aos-platform/.env then restart aos-api"
Write-Host "bootstrap-openfga OK"
exit 0
