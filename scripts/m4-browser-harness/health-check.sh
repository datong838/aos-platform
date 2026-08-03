#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STATE_DIR="${AOS_M4_STATE_DIR:-${TMPDIR:-/tmp}/aos-m4-browser-harness}"
API_PORT="${AOS_M4_API_PORT:-18080}"
PROXY_PORT="${AOS_M4_PROXY_PORT:-18081}"
WEB_PORT="${AOS_M4_WEB_PORT:-1420}"

curl -fsS "http://127.0.0.1:${API_PORT}/v1/health" >/dev/null
curl -fsS "http://127.0.0.1:${PROXY_PORT}/__harness/health" >/dev/null
curl -fsS "http://127.0.0.1:${WEB_PORT}/apollo/cases" >/dev/null

headers=(-H 'X-Org-Id: dev-org' -H 'X-Project-Id: dev-project')
curl -fsS "http://127.0.0.1:${PROXY_PORT}/v1/me" "${headers[@]}" >"$STATE_DIR/me.json"
curl -fsS "http://127.0.0.1:${PROXY_PORT}/v1/integration-cases?scope=current&limit=20&offset=0" "${headers[@]}" >"$STATE_DIR/current.json"
curl -fsS "http://127.0.0.1:${PROXY_PORT}/v1/integration-cases?scope=reference&limit=20&offset=0" "${headers[@]}" >"$STATE_DIR/reference.json"

python_bin="$(command -v python3 || command -v python)"
"$python_bin" - "$STATE_DIR" <<'PY'
import json, pathlib, sys, urllib.error, urllib.request

state = pathlib.Path(sys.argv[1])
seed = json.loads((state / "seed.json").read_text())
me = json.loads((state / "me.json").read_text())
current = json.loads((state / "current.json").read_text())
reference = json.loads((state / "reference.json").read_text())
assert me["subject"] == "operator:m4-browser" and me["tokenKind"] == "oidc"
assert current["scope"] == "current" and current["total"] == 2
assert reference["scope"] == "reference" and reference["total"] == 1
assert reference["stats"] is None
ref_item = reference["items"][0]
assert ref_item["owner"] is None and ref_item["installationId"] is None

headers = {"X-Org-Id": seed["orgId"], "X-Project-Id": seed["projectId"]}
base = "http://127.0.0.1:" + __import__("os").environ.get("AOS_M4_PROXY_PORT", "18081")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
def read_json(url):
    request = urllib.request.Request(url, headers=headers)
    try:
        with opener.open(request) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(f"{url} returned HTTP {exc.code}: {body}") from exc

for case_key in ("stableCaseId", "expiringCaseId"):
    case_id = seed[case_key]
    detail = read_json(f"{base}/v1/integration-cases/{case_id}")
    assert detail["caseId"] == case_id and len(detail["stageGates"]) == 8
    assert detail["computedStage"] in {"connection_verified", "planned"}
    timeline = read_json(f"{base}/v1/integration-cases/{case_id}/timeline?limit=20&offset=0")
    assert timeline["caseId"] == case_id and timeline["total"] >= 2
print("OK real PostgreSQL + aos-api + JWT proxy + Web; current=2 reference=1 detail/timeline=ready")
PY
