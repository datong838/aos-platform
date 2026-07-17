#Requires -Version 5.1
<#
  Preflight for Ferry large-image onsite pack — scheme 62
  Checks manifest, local image presence, optional size estimate. No copy.

  Usage:
    .\scripts\ci\probe-ferry-large-images.ps1
    .\scripts\ci\probe-ferry-large-images.ps1 -Manifest deploy\ferry\customer-images.example.json
#>
param(
    [string]$Manifest = "",
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
)

$ErrorActionPreference = "Stop"

if (-not $Manifest) {
    $Manifest = Join-Path $Root "deploy\ferry\customer-images.example.json"
}

Write-Host "probe-ferry-large-images (scheme 62)"
if (-not (Test-Path $Manifest)) {
    Write-Host "SKIP: manifest missing $Manifest"
    exit 0
}

$doc = Get-Content -Raw $Manifest | ConvertFrom-Json
$hasDocker = $false
try {
    $null = & docker version --format "{{.Server.Version}}" 2>$null
    $hasDocker = ($LASTEXITCODE -eq 0)
} catch { $hasDocker = $false }

if (-not $hasDocker) {
    Write-Host "SKIP: docker not available (manifest parse OK)"
    Write-Host "  images count=$($doc.images.Count)"
    exit 0
}

$archiveCount = 0
$missing = @()
foreach ($item in $doc.images) {
    $ref = [string]$item.ref
    if (-not $ref) { continue }
    $qid = & docker images -q $ref 2>$null
    $local = [bool]$qid
    $arch = ($item.archive -eq $true)
    if ($arch) { $archiveCount++ }
    $sizeHint = "?"
    if ($local) {
        $sz = & docker image inspect --format "{{.Size}}" $ref 2>$null
        if ($sz) { $sizeHint = ("{0:N1} MiB" -f ([double]$sz / 1MB)) }
    } else {
        $missing += $ref
    }
    Write-Host ("  {0} local={1} archive={2} size~{3} maxGiB={4}" -f $ref, $local, $arch, $sizeHint, $item.maxGiB)
}

Write-Host "archive candidates=$archiveCount missing=$($missing.Count)"
if ($missing.Count -gt 0) {
    Write-Host "HINT: docker pull <ref> then .\scripts\ci\pack-ferry-images-onsite.ps1"
}
Write-Host "probe-ferry-large-images OK"
exit 0
