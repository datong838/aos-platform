#Requires -Version 5.1
# T3.9 host-mode LiteLLM-shaped sidecar (when Docker host-port publish is flaky).
# Usage: powershell -File deploy/dev/start-llm-sidecar-host.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Prefer free host ports; stop docker publish conflicts if present
docker stop aos-dev-litellm aos-dev-llm-echo 2>$null | Out-Null

$env:AOS_LLM_UPSTREAM_BASE = "http://127.0.0.1:8081/v1"
$env:LITELLM_MASTER_KEY = "aos_dev_litellm_master"
$env:AOS_LLM_UPSTREAM_KEY = "aos_dev_upstream_only"

Start-Process python -ArgumentList "-m","uvicorn","app:app","--host","127.0.0.1","--port","8081" `
  -WorkingDirectory (Join-Path $root "llm-echo") `
  -RedirectStandardOutput (Join-Path $root "aos-echo.out.log") `
  -RedirectStandardError (Join-Path $root "aos-echo.err.log") `
  -WindowStyle Hidden

Start-Sleep -Seconds 1

Start-Process python -ArgumentList "-m","uvicorn","app:app","--host","127.0.0.1","--port","4000" `
  -WorkingDirectory (Join-Path $root "litellm") `
  -RedirectStandardOutput (Join-Path $root "aos-litellm.out.log") `
  -RedirectStandardError (Join-Path $root "aos-litellm.err.log") `
  -WindowStyle Hidden

Start-Sleep -Seconds 2
$echo = (Invoke-WebRequest "http://127.0.0.1:8081/health" -UseBasicParsing).Content
$llm = (Invoke-WebRequest "http://127.0.0.1:4000/health" -UseBasicParsing).Content
Write-Host "echo: $echo"
Write-Host "litellm: $llm"
Write-Host "Set aos-api env: AOS_LITELLM_URL=http://127.0.0.1:4000 AOS_LITELLM_FALLBACK=off AOS_LLM_MASTER_KEY=aos_dev_litellm_master"
Write-Host "RESULT: host LLM sidecar ONLINE"
