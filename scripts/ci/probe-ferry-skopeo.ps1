#Requires -Version 5.1
<#
  Ferry skopeo archive drill — scheme 59
  Skip when Docker/skopeo unavailable.

  Usage (from aos-platform):
    $env:AOS_FERRY_SKOPEO='1'
    $env:AOS_FERRY_SKOPEO_REFS='alpine:latest'
    .\scripts\ci\probe-ferry-skopeo.ps1
#>
param(
    [string]$ApiBase = "http://127.0.0.1:8080",
    [string]$SkopeoRef = "alpine:latest"
)

$ErrorActionPreference = "Stop"

function Test-Docker() {
    try {
        $null = & docker version --format "{{.Server.Version}}" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}

Write-Host "probe Ferry skopeo archive"
if (-not (Test-Docker) -and -not (Get-Command skopeo -ErrorAction SilentlyContinue)) {
    Write-Host "SKIP: neither docker nor skopeo on PATH"
    exit 0
}

# Prefer local daemon image
$img = & docker images -q $SkopeoRef 2>$null
if (-not $img) {
    Write-Host "SKIP: image $SkopeoRef not local (avoid registry pull in probe)"
    Write-Host "  docker pull $SkopeoRef   # then re-run"
    exit 0
}

$outDir = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path "deploy\dev\_skopeo_probe"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$tar = Join-Path $outDir "probe.tar"
if (Test-Path $tar) { Remove-Item $tar -Force }

$bind = "/mnt/c" + ($outDir.Substring(2) -replace '\\', '/')
# Heuristic: if path is C:\...
if ($outDir -match '^[A-Za-z]:') {
    $drive = $outDir.Substring(0, 1).ToLower()
    $rest = $outDir.Substring(2) -replace '\\', '/'
    $bind = "/mnt/$drive$rest"
}

Write-Host "skopeo via docker → $tar"
& docker run --rm `
    -v "/var/run/docker.sock:/var/run/docker.sock" `
    -v "${bind}:/out" `
    quay.io/skopeo/stable:v1.16.1 `
    copy "docker-daemon:$SkopeoRef" "docker-archive:/out/probe.tar"
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $tar)) {
    Write-Error "skopeo copy failed"
    exit 1
}
$len = (Get-Item $tar).Length
Write-Host "OK archive bytes=$len"

try {
    $st = Invoke-RestMethod -Uri "$ApiBase/v1/apollo/ferry/status" -Headers @{
        Authorization = "Bearer dev"
        "X-Org-Id" = "dev-org"
        "X-Project-Id" = "dev-project"
    } -TimeoutSec 5
    Write-Host "OK ferry status skopeoMode=$($st.skopeoMode) archiveEnabled=$($st.skopeoArchiveEnabled)"
} catch {
    Write-Warning "aos-api status not reachable (optional). Sidecar skopeo copy OK."
}

Write-Host "HINT: set AOS_FERRY_SKOPEO=1 AOS_FERRY_SKOPEO_REFS=$SkopeoRef then POST /v1/apollo/ferry/export"
Write-Host "probe-ferry-skopeo OK"
exit 0
