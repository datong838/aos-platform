#Requires -Version 5.1
# W36 · 可演示冻结快检（Windows）：demo smoke（含 l1-chain）+ Web 单测
# 用法：powershell -File scripts\demo\run-freeze-check.ps1
# 全量（pytest + 彩排）：请用 Git Bash 执行 run-freeze-check.sh --full
param(
  [switch]$Full
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")

Write-Host "=== Freeze maintenance check (W36 · Windows) ==="
& (Join-Path $PSScriptRoot "run-demo-smoke.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "--- web unit tests ---"
Push-Location (Join-Path $Root "apps\web")
try {
  npm test -- --run
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
  Pop-Location
}

if ($Full) {
  Write-Host ""
  Write-Host "WARN: --full on Windows · 请用 Git Bash:" -ForegroundColor Yellow
  Write-Host "  bash scripts/demo/run-freeze-check.sh --full"
}

Write-Host ""
Write-Host "RESULT: FREEZE CHECK OK" -ForegroundColor Green
exit 0
