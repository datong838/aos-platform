#Requires -Version 5.1
<#
  Ferry large-image onsite packer — scheme 62
  Writes archives + images.json + cosign-dev-hmac sig to disk.
  Does NOT push multi-GB blobs through aos-api export base64.

  Usage (from aos-platform):
    .\scripts\ci\pack-ferry-images-onsite.ps1 `
      -Manifest deploy\ferry\customer-images.example.json `
      -OutDir deploy\dev\_ferry_onsite

    # Only archive:true refs that exist locally (SKIP missing unless -Pull)
#>
param(
    [string]$Manifest = "",
    [string]$OutDir = "",
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$HmacSecret = "",
    [string]$SkopeoImage = "quay.io/skopeo/stable:v1.16.1",
    [int]$TimeoutSec = 900,
    [switch]$Pull,
    [switch]$SkipArchive
)

$ErrorActionPreference = "Stop"

if (-not $Manifest) {
    $Manifest = Join-Path $Root "deploy\ferry\customer-images.example.json"
}
if (-not $OutDir) {
    $OutDir = Join-Path $Root "deploy\dev\_ferry_onsite"
}
if (-not $HmacSecret) {
    if ($env:AOS_FERRY_HMAC_SECRET) { $HmacSecret = $env:AOS_FERRY_HMAC_SECRET }
    else { $HmacSecret = "aos_dev_ferry_hmac_change_me" }
}

function Test-Docker() {
    try {
        $null = & docker version --format "{{.Server.Version}}" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}

function ConvertTo-DockerBind([string]$WinPath) {
    $full = (Resolve-Path $WinPath).Path
    if ($full -match '^[A-Za-z]:') {
        $drive = $full.Substring(0, 1).ToLower()
        $rest = ($full.Substring(2) -replace '\\', '/')
        return "/mnt/$drive$rest"
    }
    return ($full -replace '\\', '/')
}

function Get-SafeArchiveName([string]$Ref) {
    $s = ($Ref -replace '[\\/:]', '_') -replace '[^a-zA-Z0-9._-]+', '_'
    if ($s.Length -gt 120) { $s = $s.Substring(0, 120) }
    return "$s.tar"
}

function Get-DockerDigest([string]$Ref) {
    $out = & docker image inspect --format "{{json .RepoDigests}}|{{.Id}}" $Ref 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $out) {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Ref)
        $sha = [System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes)
        $hex = -join ($sha | ForEach-Object { $_.ToString("x2") })
        return @{ digest = "sha256:$hex"; source = "synthetic" }
    }
    if ($out -match 'sha256:[a-f0-9]{64}') {
        return @{ digest = $Matches[0]; source = "docker-inspect" }
    }
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Ref)
    $sha = [System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes)
    $hex = -join ($sha | ForEach-Object { $_.ToString("x2") })
    return @{ digest = "sha256:$hex"; source = "synthetic" }
}

Write-Host "pack-ferry-images-onsite (scheme 62)"
if (-not (Test-Path $Manifest)) {
    Write-Error "Manifest not found: $Manifest"
    exit 1
}

$doc = Get-Content -Raw $Manifest | ConvertFrom-Json
if (-not $doc.images) {
    Write-Error "manifest.images missing"
    exit 1
}

$archDir = Join-Path $OutDir "archives"
New-Item -ItemType Directory -Force -Path $archDir | Out-Null
$images = @()
$skopeoUsed = $false
$hasDocker = Test-Docker
$hasSkopeo = [bool](Get-Command skopeo -ErrorAction SilentlyContinue)

if (-not $hasDocker -and -not $hasSkopeo -and -not $SkipArchive) {
    Write-Host "SKIP: neither docker nor skopeo (digest-only pass with -SkipArchive)"
    Write-Host "  or: docker pull <refs> then re-run"
    exit 0
}

foreach ($item in $doc.images) {
    $ref = [string]$item.ref
    if (-not $ref) { continue }
    $wantArchive = ($item.archive -eq $true)
    $maxGiB = 0
    if ($item.maxGiB) { $maxGiB = [double]$item.maxGiB }

    if ($hasDocker) {
        $qid = & docker images -q $ref 2>$null
        if (-not $qid) {
            if ($Pull) {
                Write-Host "pull $ref ..."
                & docker pull $ref
                if ($LASTEXITCODE -ne 0) {
                    Write-Warning "pull failed: $ref — skip"
                    continue
                }
            } else {
                Write-Warning "image not local: $ref (use -Pull or docker pull)"
                if ($wantArchive -and -not $SkipArchive) { continue }
            }
        }
    }

    $dig = Get-DockerDigest $ref
    $archiveRel = $null

    if ($wantArchive -and -not $SkipArchive) {
        $tarName = Get-SafeArchiveName $ref
        $tarPath = Join-Path $archDir $tarName
        if (Test-Path $tarPath) { Remove-Item $tarPath -Force }
        Write-Host "archive $ref -> $tarName"
        $ok = $false
        if ($hasSkopeo) {
            & skopeo copy "docker-daemon:$ref" "docker-archive:$tarPath"
            if ($LASTEXITCODE -eq 0 -and (Test-Path $tarPath)) { $ok = $true }
            if (-not $ok) {
                & skopeo copy "docker://$ref" "docker-archive:$tarPath"
                if ($LASTEXITCODE -eq 0 -and (Test-Path $tarPath)) { $ok = $true }
            }
        }
        if (-not $ok -and $hasDocker) {
            $bind = ConvertTo-DockerBind $archDir
            $job = Start-Job -ScriptBlock {
                param($Img, $Ref, $Bind, $Name)
                docker run --rm `
                    -v "/var/run/docker.sock:/var/run/docker.sock" `
                    -v "${Bind}:/out" `
                    $Img `
                    copy "docker-daemon:$Ref" "docker-archive:/out/$Name"
            } -ArgumentList $SkopeoImage, $ref, $bind, $tarName
            $finished = Wait-Job $job -Timeout $TimeoutSec
            if ($finished) {
                Receive-Job $job | Out-Host
                if ((Test-Path $tarPath) -and ((Get-Item $tarPath).Length -gt 0)) { $ok = $true }
            } else {
                Write-Warning "skopeo timeout ${TimeoutSec}s for $ref"
                Stop-Job $job -ErrorAction SilentlyContinue
                Remove-Job $job -Force -ErrorAction SilentlyContinue
            }
            Remove-Job $job -Force -ErrorAction SilentlyContinue
        }
        if ($ok) {
            $bytes = (Get-Item $tarPath).Length
            if ($maxGiB -gt 0 -and ($bytes / 1GB) -gt $maxGiB) {
                Write-Warning "archive $ref size $([math]::Round($bytes/1GB,2))GiB > maxGiB=$maxGiB — keep file, flag oversized"
            }
            $archiveRel = "artifacts/archives/$tarName"
            $skopeoUsed = $true
            Write-Host "  OK bytes=$bytes"
        } else {
            Write-Warning "archive failed: $ref"
        }
    }

    $images += [ordered]@{
        ref          = $ref
        digest       = $dig.digest
        digestSource = $dig.source
        archive      = $archiveRel
    }
}

$imagesDoc = [ordered]@{
    version    = "1"
    skopeoUsed = $skopeoUsed
    onsitePack = $true
    images     = $images
}
$imagesPath = Join-Path $OutDir "images.json"
$json = ($imagesDoc | ConvertTo-Json -Depth 8)
# PowerShell ConvertTo-Json may reorder; write UTF8 no BOM-ish
[System.IO.File]::WriteAllText($imagesPath, $json)

# cosign-dev-hmac: HMAC-SHA256("ferry-images:" + body) as hex — match aos_api.ferry
$hmac = New-Object System.Security.Cryptography.HMACSHA256
$hmac.Key = [System.Text.Encoding]::UTF8.GetBytes($HmacSecret)
$bodyBytes = [System.IO.File]::ReadAllBytes($imagesPath)
$prefix = [System.Text.Encoding]::UTF8.GetBytes("ferry-images:")
$payload = New-Object byte[] ($prefix.Length + $bodyBytes.Length)
[Array]::Copy($prefix, 0, $payload, 0, $prefix.Length)
[Array]::Copy($bodyBytes, 0, $payload, $prefix.Length, $bodyBytes.Length)
$hash = $hmac.ComputeHash($payload)
$sigHex = -join ($hash | ForEach-Object { $_.ToString("x2") })
$sigPath = Join-Path $OutDir "images.sig"
Set-Content -Path $sigPath -Value $sigHex -Encoding ASCII -NoNewline

$readme = @"
# Ferry onsite image pack (scheme 62)

- Manifest: $Manifest
- images.json + images.sig (cosign-dev-hmac)
- archives/: docker-archive tar files (keep beside ferry-bundle; do not base64 via API)

Import tip: ship ferry-bundle tar.gz (manifest + images.json/sig) on media A;
put large ``archives/*.tar`` on media B with the same relative paths under artifacts/.

Env for aos-api (optional digest-only):
  AOS_FERRY_IMAGES_MANIFEST=$Manifest
  AOS_FERRY_SKOPEO=0
  AOS_FERRY_SKOPEO_MAX_MIB=64
"@
Set-Content -Path (Join-Path $OutDir "README-ONSITE.md") -Value $readme -Encoding UTF8

Write-Host "OK wrote $OutDir (images=$($images.Count) skopeoUsed=$skopeoUsed)"
Write-Host "pack-ferry-images-onsite OK"
exit 0
