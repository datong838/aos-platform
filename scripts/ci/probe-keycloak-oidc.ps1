#Requires -Version 5.1
<#
  Dev Keycloak OIDC probe — scheme 50 / B-TX3-01
  Skip (exit 0) when Keycloak JWKS unreachable.

  Usage (from aos-platform):
    .\scripts\ci\probe-keycloak-oidc.ps1
    .\scripts\ci\probe-keycloak-oidc.ps1 -ApiBase http://127.0.0.1:8080
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
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        return $r.StatusCode -ge 200 -and $r.StatusCode -lt 500
    } catch {
        return $false
    }
}

Write-Host "probe Keycloak JWKS: $jwks"
if (-not (Test-Url $jwks)) {
    Write-Host "SKIP: Keycloak not up. Start with:"
    Write-Host "  docker compose -f deploy/dev/docker-compose.yml --profile oidc up -d aos-dev-keycloak"
    exit 0
}

Write-Host "OK JWKS reachable"
$form = @{
    grant_type = "password"
    client_id  = $ClientId
    username   = $Username
    password   = $Password
}
$tok = Invoke-RestMethod -Method Post -Uri $tokenUrl -Body $form -ContentType "application/x-www-form-urlencoded"
if (-not $tok.access_token) {
    Write-Error "no access_token from Keycloak"
    exit 1
}
Write-Host "OK password grant"

$hdr = @{
    Authorization = "Bearer $($tok.access_token)"
    "X-Org-Id"    = "dev-org"
    "X-Project-Id"= "dev-project"
}

# Expect aos-api env already pointed at this KC (or probe only proves IdP).
try {
    $me = Invoke-RestMethod -Method Get -Uri "$ApiBase/v1/me" -Headers $hdr
    Write-Host "OK /v1/me subject=$($me.subject) tokenKind=$($me.tokenKind)"
    if ($me.tokenKind -ne "oidc") {
        Write-Warning "tokenKind=$($me.tokenKind) — set AOS_OIDC_JWKS_URL=$jwks AOS_OIDC_ISSUER=$issuer AOS_OIDC_AUDIENCE=aos-api then restart aos-api"
    }
} catch {
    Write-Warning "/v1/me failed (aos-api may need OIDC env). IdP grant still OK. $_"
    Write-Host "HINT env:"
    Write-Host "  AOS_OIDC_ISSUER=$issuer"
    Write-Host "  AOS_OIDC_AUDIENCE=aos-api"
    Write-Host "  AOS_OIDC_JWKS_URL=$jwks"
    Write-Host "  AOS_OIDC_TOKEN_URL=$tokenUrl"
    exit 0
}

Write-Host "probe-keycloak-oidc OK"
exit 0
