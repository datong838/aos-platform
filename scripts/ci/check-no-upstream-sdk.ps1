#Requires -Version 5.1
# G3: ban UI importing upstream SDKs / reference trees (23 R-ARCH-01).
param(
  [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
  [switch]$ExpectFail
)

$web = Join-Path $Root "apps\web"
$patternsFile = Join-Path $PSScriptRoot "forbidden-ui-imports.txt"
if (-not (Test-Path $web)) {
  Write-Error "apps/web missing: $web"
  exit 2
}

$patterns = Get-Content $patternsFile | Where-Object { $_ -and -not $_.StartsWith("#") }
$files = Get-ChildItem -Path $web -Recurse -Include *.ts,*.tsx,*.js,*.jsx |
  Where-Object { $_.FullName -notmatch "node_modules|dist|\\.vite" }

if ($ExpectFail) {
  $files = $files | Where-Object { $_.FullName -match "fixtures" }
} else {
  $files = $files | Where-Object { $_.FullName -notmatch "fixtures" }
}

$hits = @()
foreach ($f in $files) {
  $text = Get-Content -Raw -Path $f.FullName
  foreach ($p in $patterns) {
    if ($text -match $p) {
      $hits += "{0} :: /{1}/" -f $f.FullName.Substring($Root.Length), $p
    }
  }
}

if ($ExpectFail) {
  if ($hits.Count -gt 0) {
    Write-Host "G3 fixture OK: intentional violations detected ($($hits.Count))"
    $hits | ForEach-Object { Write-Host "  $_" }
    exit 0
  }
  Write-Error "G3 fixture expected violations but found none"
  exit 1
}

if ($hits.Count -gt 0) {
  Write-Host "G3 FAIL: forbidden imports/paths in apps/web"
  $hits | ForEach-Object { Write-Host "  $_" }
  exit 1
}

Write-Host "G3 PASS: no forbidden UI upstream SDK imports"
exit 0
