#!/usr/bin/env bash
# W17 · Agnes LLM 回归（需 aos-platform/.env 已填 AGNES_*）
# 用法：bash scripts/demo/run-agnes-smoke.sh
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export AOS_API_BASE="${AOS_API_BASE:-http://127.0.0.1:8080}"

bash "$ROOT/scripts/demo/ensure-api.sh" --restart

# 等 API 就绪（重启后避免瞬态 mock）
for _ in $(seq 1 30); do
  if curl -sf --max-time 2 "${AOS_API_BASE}/v1/health" >/dev/null; then
    break
  fi
  sleep 1
done
sleep 2

python3 - <<PY
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Load .env the same way aos-api does
root = Path("${ROOT}")
for path in (root / ".env", root / "deploy" / "dev" / ".env"):
    if not path.is_file():
        continue
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key.startswith("AGNES_") and val:
            os.environ[key] = val
    break

for req_key in ("AGNES_API_KEY", "AGNES_BASE_URL", "AGNES_TEXT_MODEL"):
    if not os.environ.get(req_key):
        print(f"SKIP Agnes smoke — missing {req_key} in aos-platform/.env")
        sys.exit(0)

expected_model = os.environ["AGNES_TEXT_MODEL"]
BASE = os.environ.get("AOS_API_BASE", "http://127.0.0.1:8080")
HEADERS = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "Content-Type": "application/json",
}
fail = 0


def req(method, path, body=None, timeout=90):
    data = None if body is None else json.dumps(body).encode("utf-8")
    r = urllib.request.Request(BASE + path, data=data, headers=HEADERS, method=method)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def ok(name, fn):
    global fail
    try:
        fn()
        print(f"OK   {name}")
    except Exception as e:
        print(f"FAIL {name} :: {e}")
        fail += 1


def check_providers():
    p = req("GET", "/v1/aip/providers")
    if p.get("sidecar") != "agnes-openai-compatible":
        raise ValueError(f"sidecar={p.get('sidecar')}")
    if not p.get("items"):
        raise ValueError("no provider items")
    if p.get("defaultTextModel") != expected_model:
        raise ValueError(f"defaultTextModel={p.get('defaultTextModel')}")


def check_models():
    m = req("GET", "/v1/aip/models")
    if m.get("defaultTextModel") != expected_model:
        raise ValueError(f"defaultTextModel={m.get('defaultTextModel')}")


def check_chat():
    last = None
    for attempt in range(2):
        r = req("POST", "/v1/aip/chat", {"query": "用一句话说明你是哪个模型。", "withTools": False})
        if r.get("route") == "agnes":
            ans = str(r.get("answer") or "")
            if ans.startswith("[mock-llm]"):
                raise ValueError("still mock fallback")
            if not ans.strip():
                raise ValueError("empty answer")
            return
        last = r.get("route")
        if attempt == 0:
            import time
            time.sleep(3)
    raise ValueError(f"route={last}")


def check_buddy():
    r = req("POST", "/v1/buddy/ask", {
        "query": "WorkOrder wo-1001 当前风险？",
        "context": {"objectType": "WorkOrder", "objectId": "wo-1001"},
    })
    ans = str(r.get("answer") or "")
    if ans.startswith("[mock-llm]"):
        raise ValueError("buddy still mock")
    sources = r.get("sources") or []
    if sources and sources[0].get("route") != "agnes":
        raise ValueError(f"buddy route={sources[0].get('route')}")


print("=== Agnes LLM smoke ===")
print(f"model={expected_model}  base={os.environ.get('AGNES_BASE_URL', '')}")

ok("providers", check_providers)
ok("models", check_models)
ok("aip-chat", check_chat)
ok("buddy-ask", check_buddy)

print()
if fail:
    print(f"RESULT: AGNES SMOKE FAIL ({fail})")
    sys.exit(1)
print("RESULT: AGNES SMOKE OK")
PY
