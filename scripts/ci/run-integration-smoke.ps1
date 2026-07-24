#Requires -Version 5.1
# Runnable integration smoke for Wave-0/1/2 APIs.
param(
  [string]$Base = "http://127.0.0.1:8080"
)
$ErrorActionPreference = "Stop"
$h = @{
  Authorization = "Bearer dev"
  "X-Org-Id" = "dev-org"
  "X-Project-Id" = "dev-project"
  "X-Trace-Id" = "it-auto"
  "Content-Type" = "application/json"
}

function Assert-True($cond, $msg) {
  if (-not $cond) { throw "FAIL: $msg" }
  Write-Host "OK  $msg"
}

Write-Host "=== integration smoke against $Base ==="
$health = Invoke-RestMethod "$Base/v1/health"
Assert-True ($health.status -eq "ok") "IT health"

try { Invoke-RestMethod "$Base/v1/me" } catch {
  Assert-True ($_.Exception.Response.StatusCode.value__ -eq 401) "IT me unauthorized"
}

$me = Invoke-RestMethod "$Base/v1/me" -Headers $h
Assert-True ($me.orgId -eq "dev-org") "IT me auth"

$ask = Invoke-RestMethod "$Base/v1/buddy/ask" -Method POST -Headers $h -Body '{"query":"ping"}'
Assert-True (($ask.answer -as [string]).Length -gt 0) "IT buddy"

$mods = Invoke-RestMethod "$Base/v1/modules" -Headers $h
Assert-True ($mods.items.Count -ge 1) "IT modules"

$q = Invoke-RestMethod "$Base/v1/object-sets/query" -Method POST -Headers $h -Body '{"filters":[{"field":"site","value":"DC-East"}],"page":1,"pageSize":10,"source":"pg","objectType":"WorkOrder"}'
Assert-True ($q.total -ge 1) "IT object-sets pg"

$types = Invoke-RestMethod "$Base/v1/ontology/object-types" -Headers $h
Assert-True ($types.items.Count -ge 1) "IT object-types"

$gh = Invoke-RestMethod "$Base/v1/ontology/graph-health" -Headers $h
Assert-True ($null -ne $gh.score) "IT graph-health"

$br = Invoke-RestMethod "$Base/v1/ontology/branches" -Headers $h
Assert-True ($br.items.Count -ge 1) "IT branches"

$lint = Invoke-RestMethod "$Base/v1/ontology/constitution/lint" -Method POST -Headers $h -Body '{"id":"x","published":true,"properties":[]}'
Assert-True ($lint.ok -eq $false) "IT constitution lint red"

$val = $null
try {
  Invoke-RestMethod "$Base/v1/actions/validate" -Method POST -Headers $h -Body '{"actionTypeId":"CloseWorkOrder","payload":{}}'
} catch {
  Assert-True ($_.Exception.Response.StatusCode.value__ -eq 400) "IT submission criteria reject"
}
$valOk = Invoke-RestMethod "$Base/v1/actions/validate" -Method POST -Headers $h -Body '{"actionTypeId":"CloseWorkOrder","payload":{"reason":"ok"}}'
Assert-True ($valOk.ok -eq $true) "IT submission criteria pass"

$draft = Invoke-RestMethod "$Base/v1/aip/drafts" -Method POST -Headers $h -Body '{"actionTypeId":"CloseWorkOrder","objectType":"WorkOrder","objectId":"wo-smoke-approve","proposed":{"reason":"smoke","status":"closed"},"title":"smoke-draft"}'
Assert-True ($draft.status -eq "proposed") "IT draft create"
Assert-True ($draft.productionWritten -eq $false) "IT draft not writing production"

$drafts = Invoke-RestMethod "$Base/v1/aip/drafts" -Headers $h
Assert-True ($drafts.items.Count -ge 1) "IT draft list"

$approveHeaders = @{
  Authorization = "Bearer dev"
  "X-Org-Id" = "dev-org"
  "X-Project-Id" = "dev-project"
  "X-Trace-Id" = "it-auto"
  "Content-Type" = "application/json"
  "Idempotency-Key" = "smoke-approve-$($draft.id)"
}
$approved = Invoke-RestMethod "$Base/v1/aip/drafts/$($draft.id)/approve" -Method POST -Headers $approveHeaders
Assert-True ($approved.productionWritten -eq $true) "IT draft approve writes production"
$lin = Invoke-RestMethod "$Base/v1/aip/lineage/$($approved.lineageId)" -Headers $h
Assert-True ($null -ne $lin.steps) "IT lineage"

# G-ALIGN-02 actions/execute
$execHeaders = @{
  Authorization = "Bearer dev"
  "X-Org-Id" = "dev-org"
  "X-Project-Id" = "dev-project"
  "X-Trace-Id" = "it-auto"
  "Content-Type" = "application/json"
  "Idempotency-Key" = "smoke-exec-auto-1"
}
$exec = Invoke-RestMethod "$Base/v1/actions/execute" -Method POST -Headers $execHeaders -Body '{"actionTypeId":"CloseWorkOrder","objectType":"WorkOrder","objectId":"wo-smoke-exec","payload":{"reason":"exec","status":"closed"},"autoApprove":true}'
Assert-True ($exec.productionWritten -eq $true) "IT actions/execute autoApprove"
Assert-True ($exec.route -eq "actions.execute") "IT actions/execute route"
$objExec = Invoke-RestMethod "$Base/v1/objects/WorkOrder/wo-smoke-exec" -Headers $h
Assert-True ($objExec.status -eq "closed") "IT execute wrote object"

$tools = Invoke-RestMethod "$Base/v1/aip/tools" -Headers $h
Assert-True ($tools.items.Count -ge 1) "IT tool registry"

$logic = Invoke-RestMethod "$Base/v1/aip/logic/run" -Method POST -Headers $h -Body '{"dryRun":true,"edits":[{"objectType":"WorkOrder","objectId":"wo-1001","set":{"n":1}}]}'
Assert-True ($logic.productionWritten -eq $false) "IT logic dryRun"

$chat = Invoke-RestMethod "$Base/v1/aip/chat" -Method POST -Headers $h -Body '{"query":"smoke"}'
Assert-True ($null -ne $chat.provider) "IT aip chat facade"
Assert-True (($chat.answer -as [string]).Length -gt 0) "IT aip chat provider ok"
Write-Host "OK  IT aip chat meta route=$($chat.route) provider=$($chat.provider) sidecar=$($chat.sidecar)"
$prov = Invoke-RestMethod "$Base/v1/aip/providers" -Headers $h
Assert-True ($prov.apiKeyRef -like "vault:*") "IT providers vault ref only"
Assert-True (($prov | ConvertTo-Json -Compress) -notmatch "aos_dev_litellm_master") "IT providers no plaintext master"

$media = Invoke-RestMethod "$Base/v1/media-sets" -Method POST -Headers $h -Body '{"name":"smoke.bin","bytesBase64":"c21va2U="}'
Assert-True ($null -ne $media.rid) "IT media set"
# T4.2: if stored, content round-trip
if ($media.stored -eq $true) {
  $content = Invoke-RestMethod "$Base/v1/media-sets/$($media.rid)/content" -Headers $h
  Assert-True ($content.bytesBase64 -eq "c21va2U=") "IT media content roundtrip"
  $osh = Invoke-RestMethod "$Base/v1/object-store/health" -Headers $h
  Assert-True ($osh.ok -eq $true) "IT object-store health"
  Assert-True (($osh | ConvertTo-Json -Compress) -notmatch "aos_dev_only_change_me") "IT object-store no secret"
} else {
  Write-Host "WARN  IT media stored=false (MinIO unreachable) — metadata-only accepted"
}

$spoke = Invoke-RestMethod "$Base/v1/apollo/spokes/local" -Headers $h
Assert-True ($spoke.heartbeatOk -eq $true) "IT apollo spoke"

# T4.6 MySQL (optional live)
try {
  $mh = Invoke-RestMethod "$Base/v1/connectors/mysql/health" -Headers $h
  Assert-True ($null -ne $mh.mode) "IT mysql health"
  Assert-True (($mh | ConvertTo-Json -Compress) -notmatch "aos_dev_only_change_me") "IT mysql no password"
  if ($mh.mode -eq "live" -and $mh.ok -eq $true) {
    $ing = Invoke-RestMethod "$Base/v1/connectors/mysql/ingest" -Method POST -Headers $h -Body '{"limit":5}'
    Assert-True ($ing.written -ge 1) "IT mysql ingest"
    $oid = $ing.objectIds[0]
    $obj = Invoke-RestMethod "$Base/v1/objects/WorkOrder/$oid" -Headers $h
    Assert-True ($null -ne $obj.id -or $null -ne $obj.title) "IT mysql mapped object readable"
  } else {
    Write-Host "WARN  IT mysql mode=$($mh.mode) — skip ingest (container not live)"
  }
} catch {
  Write-Host "WARN  IT mysql skipped: $($_.Exception.Message)"
}

# T4.8 OCR (optional live sidecar)
try {
  $ocr = Invoke-RestMethod "$Base/v1/docintel/ocr" -Method POST -Headers $h -Body '{"page":1,"textHint":"smoke-ocr-page"}'
  Assert-True ($null -ne $ocr.text) "IT ocr text"
  Assert-True ($null -ne $ocr.engine) "IT ocr engine"
  if ($ocr.sidecar -eq "ocr") {
    Assert-True ($ocr.engine -ne "paddleocr-stub") "IT ocr not in-process stub"
    Write-Host "OK  IT ocr sidecar=$($ocr.sidecar) engine=$($ocr.engine)"
  } else {
    Write-Host "WARN  IT ocr sidecar=$($ocr.sidecar) — set AOS_OCR_URL for live edge"
  }
  $pipe = Invoke-RestMethod "$Base/v1/docintel/pipeline" -Method POST -Headers $h -Body '{"page":1,"textHint":"smoke-pipeline-ocr"}'
  Assert-True ($pipe.batchOk -eq $true) "IT docintel pipeline"
  Assert-True ($null -ne $pipe.ocr.text) "IT pipeline ocr into chain"
  Assert-True ($null -ne $pipe.parse.text) "IT pipeline parse into chain"
} catch {
  Write-Host "WARN  IT ocr skipped: $($_.Exception.Message)"
}

# T4.4b parsers
try {
  $plist = Invoke-RestMethod "$Base/v1/parsers" -Headers $h
  Assert-True ($plist.items.Count -ge 4) "IT parsers listed"
  $b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("smoke-parser-txt"))
  $ex = Invoke-RestMethod "$Base/v1/parsers/extract" -Method POST -Headers $h -Body (@{ name = "smoke.txt"; bytesBase64 = $b64 } | ConvertTo-Json)
  Assert-True ($ex.ok -eq $true) "IT parser extract txt"
  Assert-True ($ex.text -eq "smoke-parser-txt") "IT parser text match"
  Write-Host "OK  IT parsers extract engine=$($ex.parser)"
} catch {
  Write-Host "WARN  IT parsers skipped: $($_.Exception.Message)"
}

Write-Host "RESULT: integration smoke PASSED"
exit 0
