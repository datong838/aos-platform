#!/usr/bin/env bash
# TB.1 · ensure WorkOrder demo seed via API（对齐 ensure-seed.ps1）
set -euo pipefail

API="${AOS_API_BASE:-http://127.0.0.1:8080}"

curl -sf --max-time 30 -X POST "$API/v1/demo/ensure-seed" \
  -H "Authorization: Bearer dev" \
  -H "X-Org-Id: dev-org" \
  -H "X-Project-Id: dev-project" \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -c "
import json, sys
r = json.load(sys.stdin)
snap = r.get('snapshot') or {}
print(f\"OK seed objects={snap.get('objectCount', '?')} type={snap.get('objectType', '?')}\")
"
