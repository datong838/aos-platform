#Requires -Version 5.1
<#
  Probe Ferry cosign keychain — scheme 64
  Skip when no cosign/docker or no keys.

  Usage:
    .\scripts\ci\probe-ferry-cosign.ps1
#>
param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$ApiBase = "http://127.0.0.1:8080",
    [string]$Key = "",
    [string]$Pub = ""
)

$ErrorActionPreference = "Stop"

if (-not $Key) { $Key = if ($env:AOS_FERRY_COSIGN_KEY) { $env:AOS_FERRY_COSIGN_KEY } else { Join-Path $Root "deploy\dev\cosign\cosign.key" } }
if (-not $Pub) { $Pub = if ($env:AOS_FERRY_COSIGN_PUB) { $env:AOS_FERRY_COSIGN_PUB } else { Join-Path $Root "deploy\dev\cosign\cosign.pub" } }

Write-Host "probe-ferry-cosign (scheme 64)"
$hasPath = [bool](Get-Command cosign -ErrorAction SilentlyContinue)
$hasDocker = $false
try {
    $null = & docker version --format "{{.Server.Version}}" 2>$null
    $hasDocker = ($LASTEXITCODE -eq 0)
} catch { $hasDocker = $false }

if (-not $hasPath -and -not $hasDocker) {
    Write-Host "SKIP: no cosign CLI and no docker"
    exit 0
}
if (-not (Test-Path $Key) -or -not (Test-Path $Pub)) {
    Write-Host "SKIP: keys missing — run .\scripts\ci\gen-ferry-cosign-keys.ps1"
    exit 0
}

$tmp = Join-Path $env:TEMP ("aos-ferry-cosign-" + [guid]::NewGuid().ToString("n"))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$blob = Join-Path $tmp "blob.txt"
$sig = Join-Path $tmp "blob.sig"
Set-Content -Path $blob -Value "aos-ferry-cosign-probe" -Encoding ASCII -NoNewline
$env:COSIGN_PASSWORD = ""

try {
    if ($hasPath) {
        & cosign sign-blob --yes --key $Key --output-signature $sig $blob
        if ($LASTEXITCODE -ne 0) { Write-Error "sign-blob failed"; exit 1 }
        & cosign verify-blob --key $Pub --signature $sig $blob
        if ($LASTEXITCODE -ne 0) { Write-Error "verify-blob failed"; exit 1 }
    } else {
        function Bind([string]$p) {
            $full = (Resolve-Path $p).Path
            $drive = $full.Substring(0, 1).ToLower()
            $rest = ($full.Substring(2) -replace '\\', '/')
            return "/mnt/$drive$rest"
        }
        $img = if ($env:AOS_FERRY_COSIGN_IMAGE) { $env:AOS_FERRY_COSIGN_IMAGE } else { "ghcr.io/sigstore/cosign/cosign:v2.4.1" }
        $bw = Bind $tmp
        $bk = Bind (Split-Path $Key -Parent)
        $kn = Split-Path $Key -Leaf
        $pn = Split-Path $Pub -Leaf
        & docker run --rm -e COSIGN_PASSWORD= -v "${bw}:/work" -v "${bk}:/keys:ro" $img `
            sign-blob --yes --key "/keys/$kn" --output-signature /work/blob.sig /work/blob.txt
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $sig)) { Write-Error "docker sign-blob failed"; exit 1 }
        & docker run --rm -v "${bw}:/work" -v "${bk}:/keys:ro" $img `
            verify-blob --key "/keys/$pn" --signature /work/blob.sig /work/blob.txt
        if ($LASTEXITCODE -ne 0) { Write-Error "docker verify-blob failed"; exit 1 }
    }
    Write-Host "OK cosign sign+verify blob"
} finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}

try {
    $st = Invoke-RestMethod -Uri "$ApiBase/v1/apollo/ferry/status" -Headers @{
        Authorization = "Bearer dev"
        "X-Org-Id" = "dev-org"
        "X-Project-Id" = "dev-project"
    } -TimeoutSec 5
    Write-Host "OK status cosign=$($st.cosign) cli=$($st.cosignCliMode) required=$($st.cosignRequired) fullDeferred=$($st.fullChannelDeferred)"
} catch {
    Write-Warning "aos-api status optional: $_"
}

Write-Host "probe-ferry-cosign OK"
exit 0
