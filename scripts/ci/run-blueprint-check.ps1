# Blueprint live compliance check — T-UI / DEMO_PAGES / T-API / R-ARCH-01
# Run after stack is up: API :8080 · Web :5173 · LLM :4000

$ErrorActionPreference = "Stop"
$Base = "http://127.0.0.1:8080"
$Web = "http://127.0.0.1:5173"
$h = @{
  Authorization = "Bearer dev"
  "X-Org-Id" = "dev-org"
  "X-Project-Id" = "dev-project"
  "Content-Type" = "application/json"
  "X-Trace-Id" = "blueprint-check"
}

$rows = @()
function Add-Row($id, $ok, $detail) {
  $script:rows += [pscustomobject]@{ ID = $id; OK = $ok; Detail = $detail }
  $mark = if ($ok) { "PASS" } else { "FAIL" }
  Write-Host "$mark  $id  $detail"
}

# --- Runtime ---
try {
  $health = Invoke-RestMethod "$Base/v1/health"
  Add-Row "RT-API" ($health.status -eq "ok") "aos-api /v1/health"
} catch { Add-Row "RT-API" $false $_.Exception.Message }

try {
  $w = Invoke-WebRequest $Web -UseBasicParsing -TimeoutSec 5
  Add-Row "RT-WEB" ($w.StatusCode -eq 200) "apps/web :5173"
} catch { Add-Row "RT-WEB" $false $_.Exception.Message }

try {
  $llm = Invoke-RestMethod "http://127.0.0.1:4000/health"
  Add-Row "RT-LLM" ($llm.status -eq "ok") "LiteLLM-shaped sidecar :4000"
} catch { Add-Row "RT-LLM" $false $_.Exception.Message }

# --- T-API / Facade ---
try {
  $chat = Invoke-RestMethod "$Base/v1/aip/chat" -Method POST -Headers $h -Body '{"query":"blueprint"}'
  $ok = ($chat.sidecar -eq "litellm") -and ($chat.apiKeyRef -like "vault:*")
  Add-Row "BP-FACADE" $ok "chat sidecar=$($chat.sidecar) keyRef=$($chat.apiKeyRef)"
} catch { Add-Row "BP-FACADE" $false $_.Exception.Message }

try {
  $prov = Invoke-RestMethod "$Base/v1/aip/providers" -Headers $h
  $blob = $prov | ConvertTo-Json -Compress
  $ok = ($prov.apiKeyRef -like "vault:*") -and ($blob -notmatch "aos_dev_litellm_master")
  Add-Row "BP-SECRET" $ok "providers vault-only (no plaintext master)"
} catch { Add-Row "BP-SECRET" $false $_.Exception.Message }

try {
  $buddy = Invoke-RestMethod "$Base/v1/buddy/ask" -Method POST -Headers $h -Body '{"query":"blueprint-buddy"}'
  Add-Row "BP-BUDDY" ($buddy.answer -match "blueprint-buddy|litellm|mock") "buddy/ask via Facade"
} catch { Add-Row "BP-BUDDY" $false $_.Exception.Message }

# --- Ontology / Workshop data path ---
try {
  $q = Invoke-RestMethod "$Base/v1/object-sets/query" -Method POST -Headers $h -Body '{"filters":[{"field":"site","value":"DC-East"}],"page":1,"pageSize":10,"source":"pg","objectType":"WorkOrder"}'
  Add-Row "BP-INBOX" ($q.total -ge 1) "object-sets PG total=$($q.total)"
} catch { Add-Row "BP-INBOX" $false $_.Exception.Message }

try {
  $ot = Invoke-RestMethod "$Base/v1/ontology/object-types" -Headers $h
  Add-Row "BP-ONT" ($ot.items.Count -ge 1) "ontology object-types"
} catch { Add-Row "BP-ONT" $false $_.Exception.Message }

# --- Write path rules ---
try {
  Invoke-RestMethod "$Base/v1/wiki/WorkOrder/wo-1001" -Method PUT -Headers $h -Body '{"body":{}}'
  Add-Row "BP-WIKI" $false "wiki PUT should 409"
} catch {
  $code = $_.Exception.Response.StatusCode.value__
  Add-Row "BP-WIKI" ($code -eq 409) "wiki direct PUT blocked status=$code"
}

try {
  $logic = Invoke-RestMethod "$Base/v1/aip/logic/run" -Method POST -Headers $h -Body '{"dryRun":true,"edits":[]}'
  Add-Row "BP-LOGIC" ($logic.productionWritten -eq $false) "logic dryRun no production write"
} catch { Add-Row "BP-LOGIC" $false $_.Exception.Message }

# --- T-UI nav narrative (section order) ---
$navPath = "c:\work\projects\wchat\aos-platform\apps\web\src\nav.ts"
$navText = Get-Content $navPath -Raw
$sections = [regex]::Matches($navText, "section:\s*`"([^`"]+)`"") | ForEach-Object { $_.Groups[1].Value }
$expected = @("工作台 L3", "AIP 决策引擎", "本体 · 数字孪生", "数据集成", "交付 Apollo")
$orderOk = ($sections.Count -ge 5)
for ($i = 0; $i -lt $expected.Count; $i++) {
  if ($sections[$i] -ne $expected[$i]) { $orderOk = $false }
}
Add-Row "BP-NAV-SECTIONS" $orderOk ("nav sections: " + ($sections -join " → "))

# required page ids present
$needIds = @("index","workshop","workshop-module","workshop-canvas","workshop-publish","workshop-aip-chat","aip-draft-inbox","aip-logic","aip-capabilities","ontology","data-connection","apollo-hub")
$missing = @()
foreach ($id in $needIds) {
  if ($navText -notmatch "id:\s*`"$id`"") { $missing += $id }
}
Add-Row "BP-NAV-IDS" ($missing.Count -eq 0) $(if ($missing.Count -eq 0) { "core DEMO ids mapped" } else { "missing: $($missing -join ',')" })

# Appearance
$appTs = Get-Content "c:\work\projects\wchat\aos-platform\apps\web\src\lib\appearance.ts" -Raw
Add-Row "BP-APPEARANCE" (($appTs -match 'aos-appearance') -and ($appTs -match 'data-aos-theme')) "Appearance key + data-aos-theme"

# R-ARCH-01: web must not import upstream SDKs
$webSrc = "c:\work\projects\wchat\aos-platform\apps\web\src"
$hits = Select-String -Path (Join-Path $webSrc "*.ts*"),(Join-Path $webSrc "**\*.ts*"),(Join-Path $webSrc "**\*.tsx") -Pattern "from ['`"]openai|from ['`"]litellm|from ['`"]@anthropic|from ['`"]airbyte" -SimpleMatch:$false -ErrorAction SilentlyContinue
# safer: ripgrep-like
$bad = @()
Get-ChildItem $webSrc -Recurse -Include *.ts,*.tsx | Where-Object { $_.FullName -notmatch "\\fixtures\\|forbidden-import" } | ForEach-Object {
  $c = Get-Content $_.FullName -Raw
  if ($c -match "from ['`"]openai|from ['`"]litellm|airbyte|@anthropic") { $bad += $_.FullName }
}
Add-Row "BP-NO-SDK" ($bad.Count -eq 0) $(if ($bad.Count -eq 0) { "web src no upstream SDK import (fixtures excluded)" } else { ($bad -join ";") })

# Demo html still present as blueprint source
$htmlDemo = "c:\work\projects\wchat\docs\palantier\foundry\html\assets\demo.js"
Add-Row "BP-HTML-SRC" (Test-Path $htmlDemo) "foundry/html demo.js exists"

$fail = @($rows | Where-Object { -not $_.OK }).Count
Write-Host ""
Write-Host "RESULT: blueprint check  pass=$($rows.Count - $fail) fail=$fail total=$($rows.Count)"
if ($fail -gt 0) { exit 1 } else { exit 0 }
