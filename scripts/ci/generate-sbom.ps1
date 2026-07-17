#Requires -Version 5.1
<#
  T0.10 — minimal CycloneDX-lite SBOM for aos-platform (Dev artifact).
  Sources: web package.json · aos-api pyproject · deploy/dev compose images.

  Usage:
    .\scripts\ci\generate-sbom.ps1
#>
param(
  [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
  [string]$OutFile = ""
)

$ErrorActionPreference = "Stop"
if (-not $OutFile) {
  $OutFile = Join-Path $Root "deploy\dev\sbom-dev.json"
}

$components = @()

function New-Comp([string]$Type, [string]$Name, [string]$Version, [string]$Scope, [string]$Purl) {
  return [pscustomobject]@{
    type    = $Type
    name    = $Name
    version = $(if ($Version) { $Version } else { "unknown" })
    scope   = $Scope
    purl    = $Purl
  }
}

# --- npm ---
$pkgPath = Join-Path $Root "apps\web\package.json"
if (Test-Path $pkgPath) {
  $pkg = Get-Content -Raw $pkgPath | ConvertFrom-Json
  foreach ($sec in @("dependencies", "devDependencies")) {
    $bag = $pkg.$sec
    if (-not $bag) { continue }
    $bag.PSObject.Properties | ForEach-Object {
      $ver = ([string]$_.Value).TrimStart("^~")
      $scope = if ($sec -eq "devDependencies") { "optional" } else { "required" }
      $script:components += New-Comp "library" $_.Name $ver $scope ("pkg:npm/{0}@{1}" -f $_.Name, $ver)
    }
  }
}

# --- python pyproject ---
$pyPath = Join-Path $Root "services\aos-api\pyproject.toml"
if (Test-Path $pyPath) {
  $raw = Get-Content -Raw $pyPath
  $inDeps = $false
  foreach ($line in ($raw -split "`n")) {
    $t = $line.Trim()
    if ($t -match '^dependencies\s*=\s*\[') { $inDeps = $true; continue }
    if ($inDeps) {
      if ($t -eq "]") { $inDeps = $false; continue }
      if ($t -match '^"([^"]+)"') {
        $spec = $Matches[1]
        $name = ($spec -split '[><=! ]')[0]
        $ver = if ($spec -match '>=\s*([0-9][^\s"]*)') { $Matches[1] } else { "unknown" }
        $script:components += New-Comp "library" $name $ver "required" ("pkg:pypi/{0}@{1}" -f $name, $ver)
      }
    }
  }
}

# --- compose images (dev-prereq) ---
$compose = Join-Path $Root "deploy\dev\docker-compose.yml"
if (Test-Path $compose) {
  Get-Content $compose | ForEach-Object {
    if ($_ -match '^\s*image:\s*(.+)$') {
      $img = $Matches[1].Trim().Trim('"')
      $name = $img
      $ver = "latest"
      if ($img -match '^(.+):(.+)$') {
        $name = $Matches[1]
        $ver = $Matches[2]
      }
      $script:components += New-Comp "container" $name $ver "dev-prereq" ("pkg:docker/{0}@{1}" -f $name, $ver)
    }
  }
}

$doc = [pscustomobject]@{
  bomFormat    = "CycloneDX"
  specVersion  = "1.5"
  version      = 1
  metadata     = [pscustomobject]@{
    timestamp = (Get-Date).ToUniversalTime().ToString("o")
    component = [pscustomobject]@{
      type    = "application"
      name    = "aos-platform"
      version = "0.3.0-dev"
    }
    tools     = @(
      [pscustomobject]@{ vendor = "aos"; name = "generate-sbom.ps1"; version = "1.0" }
    )
    note      = "Dev SBOM; deploy/dev images are customer-prereq / NOT for customer AOS package (23)"
  }
  components   = $components
}

$outDir = Split-Path $OutFile -Parent
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }
($doc | ConvertTo-Json -Depth 8) | Set-Content -Path $OutFile -Encoding UTF8
Write-Host "Wrote $OutFile ($($components.Count) components)"
exit 0
