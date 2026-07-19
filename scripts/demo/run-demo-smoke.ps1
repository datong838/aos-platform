#Requires -Version 5.1
# TB.0～TB.8 · demo smoke (API surface)
$ErrorActionPreference = "Stop"
$fail = 0
$headers = @{
  Authorization = "Bearer dev"
  "X-Org-Id" = "dev-org"
  "X-Project-Id" = "dev-project"
  "Content-Type" = "application/json"
}

function Ok([string]$Name, [scriptblock]$Block) {
  try {
    & $Block
    Write-Host "OK   $Name"
  } catch {
    Write-Host "FAIL $Name :: $($_.Exception.Message)" -ForegroundColor Red
    $script:fail++
  }
}

Write-Host "=== TB demo smoke ==="
Ok "health" { Invoke-RestMethod "http://127.0.0.1:8080/v1/health" | Out-Null }
Ok "ensure-seed" {
  Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/v1/demo/ensure-seed" -Headers $headers -Body "{}" | Out-Null
}
Ok "story" {
  $s = Invoke-RestMethod -Uri "http://127.0.0.1:8080/v1/demo/story" -Headers $headers
  if ($s.snapshot.objectCount -lt 1) { throw "no objects" }
  if (-not $s.deferred.apolloOps) { throw "apolloOps flag missing" }
}
Ok "object-sets" {
  $body = '{"objectType":"WorkOrder","filters":[{"field":"site","value":"DC-East"}],"pageSize":5}'
  $r = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/v1/object-sets/query" -Headers $headers -Body $body
  if (-not $r.items) { throw "empty items" }
}
Ok "run-story" {
  $r = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/v1/demo/run-story" -Headers $headers -Body "{}"
  if (-not $r.productionWritten) { throw "not written" }
  if ($r.before.status -eq $r.after.status) { throw "status unchanged" }
}
Ok "datasets-builds-dlq" {
  $ds = Invoke-RestMethod -Uri "http://127.0.0.1:8080/v1/datasets" -Headers $headers
  if (-not $ds.items -or $ds.items.Count -lt 1) { throw "no datasets (ensure-seed should plant demo)" }
  $b = Invoke-RestMethod -Uri "http://127.0.0.1:8080/v1/builds" -Headers $headers
  if (-not $b.items -or $b.items.Count -lt 1) { throw "no builds" }
  $d = Invoke-RestMethod -Uri "http://127.0.0.1:8080/v1/dlq" -Headers $headers
  if (-not $d.items -or $d.items.Count -lt 1) { throw "no dlq sample" }
}
Ok "l1-chain" {
  $src = Invoke-RestMethod -Uri "http://127.0.0.1:8080/v1/sources" -Headers $headers
  if (-not $src.items -or $src.items.Count -lt 1) { throw "no sources" }
  $srcIds = @($src.items | ForEach-Object { $_.id })
  $syncs = Invoke-RestMethod -Uri "http://127.0.0.1:8080/v1/syncs" -Headers $headers
  $syncLinked = @($syncs.items | Where-Object { $srcIds -contains $_.sourceId })
  if ($syncLinked.Count -lt 1) { throw "no sync linked to demo source" }
  $pipes = Invoke-RestMethod -Uri "http://127.0.0.1:8080/v1/pipelines" -Headers $headers
  $pipeLinked = @($pipes.items | Where-Object { $srcIds -contains $_.sourceId })
  if ($pipeLinked.Count -lt 1) { throw "no pipeline linked to demo source" }
}
Ok "funnel" {
  Invoke-RestMethod -Uri "http://127.0.0.1:8080/v1/funnel/WorkOrder/status" -Headers $headers | Out-Null
}
Ok "buddy" {
  $body = '{"query":"WorkOrder risk for wo-1001?","context":{"objectType":"WorkOrder","objectId":"wo-1001"}}'
  Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/v1/buddy/ask" -Headers $headers -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) -ContentType "application/json; charset=utf-8" | Out-Null
}
Ok "governance" {
  $g = Invoke-RestMethod -Uri "http://127.0.0.1:8080/v1/demo/governance" -Headers $headers
  if ($g.asPublicViewer.redactedFields -notcontains "internalCost") { throw "expected internalCost redacted" }
  if ($g.markingForbidden.code -ne "FORBIDDEN") { throw "expected FORBIDDEN" }
}
Ok "run-capability" {
  $c = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/v1/demo/run-capability" -Headers $headers -Body "{}"
  if (-not $c.job.mediaRid) { throw "no capability mediaRid" }
  if (-not $c.parser.ok) { throw "parser extract failed" }
}
Ok "run-analytics-story" {
  $a = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/v1/demo/run-analytics-story" -Headers $headers -Body "{}"
  if (-not $a.ok) { throw "analytics story not ok" }
  if (-not $a.productionWritten) { throw "not written" }
  if (-not $a.draftId) { throw "no draftId" }
  if (-not $a.lineageId) { throw "no lineageId" }
  if ([int]$a.read.total -lt 1) { throw "read.total < 1" }
  if ($a.before.status -eq $a.after.status) { throw "status unchanged" }
  if (-not $a.exportProbePublic.expected) { throw "export probe should expect FORBIDDEN" }
}
Ok "modules" { Invoke-RestMethod -Uri "http://127.0.0.1:8080/v1/modules" -Headers $headers | Out-Null }

Write-Host ""
if ($fail -eq 0) {
  Write-Host "RESULT: DEMO SMOKE OK" -ForegroundColor Green
  exit 0
}
Write-Host "RESULT: DEMO SMOKE FAIL ($fail)" -ForegroundColor Red
exit 1
