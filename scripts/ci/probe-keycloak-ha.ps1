#Requires -Version 5.1
<#
  Dev HA Keycloak probe — scheme 57 / B-TX3-01
  Skip (exit 0) when LB JWKS unreachable.

  Usage (from aos-platform):
    .\scripts\ci\probe-keycloak-ha.ps1
    # Start: docker compose -f deploy/dev/docker-compose.yml --profile oidc-ha up -d
    # Stop single-node oidc first if :8083 is taken.
#>
param(
    [string]$KeycloakBase = "http://127.0.0.1:8083",
    [string]$Realm = "aos",
    [string]$ApiBase = "http://127.0.0.1:8080",
    [string]$Username = "alice",
    [string]$Password = "aos_dev_only_change_me",
    [string]$ClientId = "aos-api"
)

$ErrorActionPreference = "Stop"
$jwks = "$KeycloakBase/realms/$Realm/protocol/openid-connect/certs"
$tokenUrl = "$KeycloakBase/realms/$Realm/protocol/openid-connect/token"
$issuer = "$KeycloakBase/realms/$Realm"

function Test-Url([string]$Url) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 8
        return $r.StatusCode -ge 200 -and $r.StatusCode -lt 500
    } catch {
        return $false
    }
}

Write-Host "probe HA Keycloak JWKS (LB): $jwks"
if (-not (Test-Url $jwks)) {
    Write-Host "SKIP: HA Keycloak LB not up. Start with:"
    Write-Host "  docker compose -f deploy/dev/docker-compose.yml --profile oidc down"
    Write-Host "  docker compose -f deploy/dev/docker-compose.yml --profile oidc-ha up -d"
    exit 0
}

Write-Host "OK LB JWKS reachable"
$form = @{
    grant_type = "password"
    client_id  = $ClientId
    username   = $Username
    password   = $Password
}
$tok = Invoke-RestMethod -Method Post -Uri $tokenUrl -Body $form -ContentType "application/x-www-form-urlencoded"
if (-not $tok.access_token) {
    Write-Error "no access_token from HA Keycloak LB"
    exit 1
}
Write-Host "OK password grant via LB"

$hdr = @{
    Authorization = "Bearer $($tok.access_token)"
    "X-Org-Id"    = "dev-org"
    "X-Project-Id"= "dev-project"
}

Write-Host "HINT aos-api env for HA:"
Write-Host "  AOS_OIDC_ISSUER=$issuer"
Write-Host "  AOS_OIDC_ISSUERS=$issuer"
Write-Host "  AOS_OIDC_AUDIENCE=aos-api"
Write-Host "  AOS_OIDC_JWKS_URLS=$jwks"
Write-Host "  AOS_OIDC_TOKEN_URL=$tokenUrl"

try {
    $me = Invoke-RestMethod -Method Get -Uri "$ApiBase/v1/me" -Headers $hdr
    Write-Host "OK /v1/me subject=$($me.subject) tokenKind=$($me.tokenKind)"
} catch {
    Write-Warning "/v1/me failed (set env above + restart aos-api). IdP LB grant still OK."
    exit 0
}

Write-Host "probe-keycloak-ha OK"
exit 0
