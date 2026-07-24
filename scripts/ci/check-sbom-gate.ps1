#Requires -Version 5.1
<#
  T0.10 — SBOM / delivery gate (23 §5 · 73 License).
  - AGPL denied images outside deploy/dev & docs
  - AGPL denied package names in SBOM / product manifests
  - Forbidden refs/ToolJet paths in product source
  - Extra scan if dist/customer exists

  Usage:
    .\scripts\ci\check-sbom-gate.ps1
    .\scripts\ci\check-sbom-gate.ps1 -Strict
    .\scripts\ci\check-sbom-gate.ps1 -GenerateFirst -Strict
#>
param(
  [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
  [switch]$Strict,
  [switch]$GenerateFirst,
  [switch]$WithTools,
  [switch]$RequireTools,
  [switch]$SkipDockerPull
)

$ErrorActionPreference = "Stop"

if ($GenerateFirst) {
  & (Join-Path $PSScriptRoot "generate-sbom.ps1") -Root $Root
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  & (Join-Path $PSScriptRoot "record-aos-deps.ps1") -Root $Root
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if ($WithTools) {
  & (Join-Path $PSScriptRoot "run-syft-trivy.ps1") `
    -Root $Root `
    -Strict:$Strict `
    -RequireTools:$RequireTools `
    -SkipDockerPull:$SkipDockerPull
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$deniedFile = Join-Path $PSScriptRoot "agpl-denied-images.txt"
$pkgFile = Join-Path $PSScriptRoot "agpl-denied-packages.txt"
$pathFile = Join-Path $PSScriptRoot "forbidden-product-paths.txt"
$denied = @(Get-Content $deniedFile | Where-Object { $_ -and -not $_.StartsWith("#") })
$deniedPkgs = @(Get-Content $pkgFile | Where-Object { $_ -and -not $_.StartsWith("#") })
$pathPatterns = @(Get-Content $pathFile | Where-Object { $_ -and -not $_.StartsWith("#") })

$hits = New-Object System.Collections.Generic.List[string]

function Add-Hit([string]$msg) { $hits.Add($msg) | Out-Null }

# --- 1) scan text files for denied image names outside allow dirs ---
$allowDirRx = '[\\/](deploy[\\/]dev|docs[\\/]|scripts[\\/]ci|node_modules|\.git)[\\/]'
$scanRoots = @(
  (Join-Path $Root "apps"),
  (Join-Path $Root "services"),
  (Join-Path $Root "packages")
)
$customerDist = Join-Path $Root "dist\customer"
if (Test-Path $customerDist) { $scanRoots += $customerDist }

$ext = @("*.yml", "*.yaml", "*.Dockerfile", "Dockerfile*", "*.ps1", "*.sh", "*.md", "*.toml", "*.json", "*.ts", "*.tsx", "*.py")
foreach ($sr in $scanRoots) {
  if (-not (Test-Path $sr)) { continue }
  Get-ChildItem -Path $sr -Recurse -File -Include $ext -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch 'node_modules|[\\/]dist[\\/]|\.vite|[\\/]\.egg-info[\\/]' } |
    ForEach-Object {
      $rel = $_.FullName.Substring($Root.Length)
      if ($rel -match $allowDirRx) { return }
      if ($_.FullName -match '[\\/]deploy[\\/]dev[\\/]') { return }
      # Ferry inventories skopeo refs including AGPL images for air-gap policy — not a product COPY
      if ($_.FullName -match '[\\/]ferry\.py$') { return }
      $text = Get-Content -Raw -Path $_.FullName -ErrorAction SilentlyContinue
      if (-not $text) { return }
      foreach ($d in $denied) {
        if ($text -match [regex]::Escape($d)) {
          Add-Hit ("AGPL_IMAGE {0} :: {1}" -f $rel, $d)
        }
      }
    }
}

# --- 2) product source path blacklist ---
$prodRoots = @(
  (Join-Path $Root "apps"),
  (Join-Path $Root "services"),
  (Join-Path $Root "packages")
)
$codeExt = @("*.ts", "*.tsx", "*.js", "*.jsx", "*.py", "*.toml", "*.yml", "*.yaml", "Dockerfile*")
foreach ($sr in $prodRoots) {
  if (-not (Test-Path $sr)) { continue }
  Get-ChildItem -Path $sr -Recurse -File -Include $codeExt -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch 'node_modules|[\\/]dist[\\/]|\.vite|fixtures|[\\/]tests[\\/]|[\\/]\.egg-info[\\/]' } |
    ForEach-Object {
      $rel = $_.FullName.Substring($Root.Length)
      $text = Get-Content -Raw -Path $_.FullName -ErrorAction SilentlyContinue
      if (-not $text) { return }
      foreach ($p in $pathPatterns) {
        if ($text -match $p) {
          Add-Hit ("FORBIDDEN_PATH {0} :: /{1}/" -f $rel, $p)
        }
      }
    }
}

# --- 3) customer SBOM only: deny AGPL server package names ---
# deploy/dev/*.json may inventory Dev/Ferry images — not a customer-package fail.
$sbomCandidates = @()
$customerSbomDir = Join-Path $Root "dist\customer"
if (Test-Path $customerSbomDir) {
  $sbomCandidates += Get-ChildItem -Path $customerSbomDir -Recurse -Filter "*sbom*.json" -ErrorAction SilentlyContinue |
    ForEach-Object { $_.FullName }
}
foreach ($sbom in $sbomCandidates) {
  if (-not (Test-Path $sbom)) { continue }
  $raw = Get-Content -Raw -Path $sbom -ErrorAction SilentlyContinue
  if (-not $raw) { continue }
  $rel = $sbom.Substring($Root.Length)
  foreach ($pkg in $deniedPkgs) {
    $rx = '(?i)("name"\s*:\s*"[^"]*' + [regex]::Escape($pkg) + '[^"]*"|"purl"\s*:\s*"[^"]*' + [regex]::Escape($pkg) + '[^"]*")'
    if ($raw -match $rx) {
      Add-Hit ("AGPL_PKG_SBOM {0} :: {1}" -f $rel, $pkg)
    }
  }
}

# --- 4) product lockfiles / manifests ---
$manifestNames = @("package-lock.json", "pnpm-lock.yaml", "requirements.txt", "pyproject.toml", "poetry.lock")
foreach ($sr in $prodRoots) {
  if (-not (Test-Path $sr)) { continue }
  Get-ChildItem -Path $sr -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object {
      ($manifestNames -contains $_.Name -or $_.Name -like "requirements*.txt") -and
      ($_.FullName -notmatch 'node_modules|[\\/]dist[\\/]')
    } |
    ForEach-Object {
      $rel = $_.FullName.Substring($Root.Length)
      $text = Get-Content -Raw -Path $_.FullName -ErrorAction SilentlyContinue
      if (-not $text) { return }
      foreach ($pkg in $deniedPkgs) {
        if ($text -match ('(?i)(^|[\s"/@])' + [regex]::Escape($pkg) + '([/\s":@]|$)')) {
          Add-Hit ("AGPL_PKG_MANIFEST {0} :: {1}" -f $rel, $pkg)
        }
      }
    }
}

# --- 5) SBOM file presence hint ---
$sbomMain = Join-Path $Root "deploy\dev\sbom-dev.json"
if (-not (Test-Path $sbomMain)) {
  Add-Hit "SBOM_MISSING deploy/dev/sbom-dev.json (run generate-sbom.ps1)"
}

if ($hits.Count -eq 0) {
  Write-Host "T0.10 PASS: SBOM gate clean (AGPL server images/packages blocked)"
  exit 0
}

Write-Host ("T0.10 hits ({0}):" -f $hits.Count)
$hits | ForEach-Object { Write-Host "  $_" }

if ($Strict) {
  Write-Error "T0.10 Strict: gate failed"
  exit 1
}
Write-Host "T0.10 WARN: non-strict (exit 0)"
exit 0
