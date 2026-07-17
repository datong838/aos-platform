#Requires -Version 5.1
<#
  Generate Dev cosign keypair for Ferry images layer — scheme 64
  Writes deploy/dev/cosign/cosign.key + cosign.pub (gitignored).
  Empty password for local Dev only — never commit keys.

  Usage (from aos-platform):
    .\scripts\ci\gen-ferry-cosign-keys.ps1
#>
param(
    [string]$OutDir = "",
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$CosignImage = "ghcr.io/sigstore/cosign/cosign:v2.4.1"
)

$ErrorActionPreference = "Stop"
if (-not $OutDir) {
    $OutDir = Join-Path $Root "deploy\dev\cosign"
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function ConvertTo-DockerBind([string]$WinPath) {
    $full = (Resolve-Path $WinPath).Path
    if ($full -match '^[A-Za-z]:') {
        $drive = $full.Substring(0, 1).ToLower()
        $rest = ($full.Substring(2) -replace '\\', '/')
        return "/mnt/$drive$rest"
    }
    return ($full -replace '\\', '/')
}

Write-Host "gen-ferry-cosign-keys -> $OutDir"
$env:COSIGN_PASSWORD = ""

$hasPath = [bool](Get-Command cosign -ErrorAction SilentlyContinue)
if ($hasPath) {
    Push-Location $OutDir
    try {
        & cosign generate-key-pair
        if ($LASTEXITCODE -ne 0) { Write-Error "cosign generate-key-pair failed"; exit 1 }
    } finally {
        Pop-Location
    }
} else {
    $hasDocker = $false
    try {
        $null = & docker version --format "{{.Server.Version}}" 2>$null
        $hasDocker = ($LASTEXITCODE -eq 0)
    } catch { $hasDocker = $false }
    if (-not $hasDocker) {
        Write-Host "SKIP: neither cosign nor docker available"
        exit 0
    }
    $bind = ConvertTo-DockerBind $OutDir
    Write-Host "Pulling $CosignImage (may be slow)..."
    $pullJob = Start-Job -ScriptBlock { param($Img) docker pull $Img } -ArgumentList $CosignImage
    $pulled = Wait-Job $pullJob -Timeout 180
    if (-not $pulled) {
        Stop-Job $pullJob -ErrorAction SilentlyContinue
        Remove-Job $pullJob -Force -ErrorAction SilentlyContinue
        Write-Host "SKIP: docker pull timed out (180s) — install PATH cosign or retry later"
        exit 0
    }
    Receive-Job $pullJob | Out-Host
    Remove-Job $pullJob -Force -ErrorAction SilentlyContinue
    & docker run --rm -e COSIGN_PASSWORD= -v "${bind}:/work" -w /work $CosignImage generate-key-pair
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "docker cosign generate-key-pair failed — SKIP"
        exit 0
    }
}

$key = Join-Path $OutDir "cosign.key"
$pub = Join-Path $OutDir "cosign.pub"
if (-not (Test-Path $key) -or -not (Test-Path $pub)) {
    Write-Error "expected cosign.key and cosign.pub under $OutDir"
    exit 1
}

Write-Host "OK key=$key"
Write-Host "OK pub=$pub"
Write-Host "HINT: set in .env (Dev only):"
Write-Host "  AOS_FERRY_COSIGN_KEY=$key"
Write-Host "  AOS_FERRY_COSIGN_PUB=$pub"
Write-Host "  AOS_FERRY_COSIGN_REQUIRED=0"
Write-Host "gen-ferry-cosign-keys OK"
exit 0
