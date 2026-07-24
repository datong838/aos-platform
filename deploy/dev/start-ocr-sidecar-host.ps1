# T4.8 host-mode OCR sidecar (when Docker host-port publish is flaky).
# Usage: powershell -File deploy/dev/start-ocr-sidecar-host.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Sidecar = Join-Path $Root "ocr-sidecar"

Push-Location $Sidecar
try {
  python -c "import fastapi,uvicorn" 2>$null
  if ($LASTEXITCODE -ne 0) {
    pip install fastapi==0.115.6 uvicorn==0.34.0 pydantic==2.10.4
  }
  Start-Process python -ArgumentList "-m","uvicorn","app:app","--host","127.0.0.1","--port","8082" `
    -WorkingDirectory $Sidecar -WindowStyle Hidden
} finally {
  Pop-Location
}

Start-Sleep -Seconds 2
$h = (Invoke-WebRequest "http://127.0.0.1:8082/health" -UseBasicParsing).Content
Write-Host "OCR health: $h"
Write-Host "Set aos-api env: AOS_OCR_URL=http://127.0.0.1:8082 AOS_OCR_FALLBACK=off"
Write-Host "RESULT: host OCR sidecar ONLINE"
