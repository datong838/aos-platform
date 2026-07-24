#Requires -Version 5.1
<#
  Production IdP connectivity checklist — scheme 60
  Does NOT start Keycloak. Validates discovery/JWKS/(optional) /v1/me.

  Usage (from aos-platform):
    .\scripts\ci\probe-prod-idp.ps1 -Issuer https://idp.example/realms/aos `
      -JwksUrl https://idp.example/realms/aos/protocol/openid-connect/certs `
      -Audience aos-api

    # With a real access token:
    .\scripts\ci\probe-prod-idp.ps1 ... -AccessToken $env:AOS_PROBE_TOKEN -ApiBase http://127.0.0.1:8080
#>
param(
    [string]$Issuer = "",
    [string]$JwksUrl = "",
    [string]$Audience = "aos-api",
    [string]$AccessToken = "",
    [string]$ApiBase = "http://127.0.0.1:8080",
    [switch]$RequireMe
)

$ErrorActionPreference = "Stop"

if (-not $Issuer -and $env:AOS_OIDC_ISSUER) { $Issuer = $env:AOS_OIDC_ISSUER }
if (-not $JwksUrl -and $env:AOS_OIDC_JWKS_URL) { $JwksUrl = $env:AOS_OIDC_JWKS_URL }
if (-not $JwksUrl -and $env:AOS_OIDC_JWKS_URLS) {
    $JwksUrl = ($env:AOS_OIDC_JWKS_URLS -split ",")[0].Trim()
}
if ($env:AOS_OIDC_AUDIENCE) { $Audience = $env:AOS_OIDC_AUDIENCE }
if (-not $AccessToken -and $env:AOS_PROBE_TOKEN) { $AccessToken = $env:AOS_PROBE_TOKEN }

function Test-Url([string]$Url) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 10
        return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500)
    } catch {
        return $false
    }
}

Write-Host "probe-prod-idp (scheme 60)"
if (-not $Issuer -or -not $JwksUrl) {
    Write-Host "SKIP: set -Issuer and -JwksUrl (or AOS_OIDC_ISSUER / AOS_OIDC_JWKS_URL)"
    Write-Host "See docs/palantier/20_tech/60-生产IdP联调手册.md"
    exit 0
}

$discovery = ($Issuer.TrimEnd("/") + "/.well-known/openid-configuration")
Write-Host "1) discovery: $discovery"
if (Test-Url $discovery) {
    Write-Host "   OK"
} else {
    Write-Warning "   discovery not reachable (some IdPs hide it; continue to JWKS)"
}

Write-Host "2) JWKS: $JwksUrl"
if (-not (Test-Url $JwksUrl)) {
    Write-Error "JWKS unreachable — fix network/TLS before pointing aos-api"
    exit 1
}
Write-Host "   OK"

Write-Host "3) aos-api public config (optional)"
try {
    $cfg = Invoke-RestMethod -Uri "$ApiBase/v1/auth/oidc" -TimeoutSec 5
    Write-Host "   issuer=$($cfg.issuer) haMode=$($cfg.haMode) allowDev=$($cfg.allowDevToken)"
    if ($cfg.allowDevToken) {
        Write-Warning "   production should set AOS_AUTH_ALLOW_DEV=0"
    }
} catch {
    Write-Warning "   aos-api /v1/auth/oidc not reachable (ok if API not up yet)"
}

Write-Host "4) /v1/me with access token"
if (-not $AccessToken) {
    Write-Host "   SKIP: pass -AccessToken or AOS_PROBE_TOKEN"
    if ($RequireMe) {
        Write-Error "RequireMe set but no token"
        exit 1
    }
    Write-Host "probe-prod-idp OK (partial)"
    exit 0
}

try {
    $me = Invoke-RestMethod -Method Get -Uri "$ApiBase/v1/me" -Headers @{
        Authorization   = "Bearer $AccessToken"
        "X-Org-Id"      = "dev-org"
        "X-Project-Id"  = "dev-project"
    } -TimeoutSec 10
    Write-Host "   OK subject=$($me.subject) tokenKind=$($me.tokenKind) org=$($me.orgId)"
    if ($me.tokenKind -eq "dev") {
        Write-Warning "   tokenKind=dev — not a production IdP JWT"
    }
} catch {
    Write-Error "/v1/me failed: $_"
    Write-Host "HINT: check iss/aud/JWKS · clock · AOS_AUTH_ALLOW_DEV=0 · claim mappers (handbook §8)"
    exit 1
}

Write-Host "probe-prod-idp OK"
Write-Host "audience expected: $Audience"
exit 0
