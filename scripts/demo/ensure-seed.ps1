#Requires -Version 5.1
# TB.1 · ensure WorkOrder demo seed via API
$ErrorActionPreference = "Stop"
$headers = @{
  Authorization = "Bearer dev"
  "X-Org-Id" = "dev-org"
  "X-Project-Id" = "dev-project"
  "Content-Type" = "application/json"
}
$r = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/v1/demo/ensure-seed" -Headers $headers -Body "{}"
Write-Host ("OK seed objects={0} type={1}" -f $r.snapshot.objectCount, $r.snapshot.objectType)
exit 0
