#!/usr/bin/env bash
# TB.0～TB.8 · demo smoke (API surface) — 对齐 run-demo-smoke.ps1
set -uo pipefail

export AOS_API_BASE="${AOS_API_BASE:-http://127.0.0.1:8080}"

python3 - <<PY
import json
import os
import sys
import urllib.request

BASE = os.environ.get("AOS_API_BASE", "http://127.0.0.1:8080")
HEADERS = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "Content-Type": "application/json",
}
fail = 0


def req(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    r = urllib.request.Request(BASE + path, data=data, headers=HEADERS, method=method)
    with urllib.request.urlopen(r, timeout=30) as resp:
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


def check_story():
    s = req("GET", "/v1/demo/story")
    if s["snapshot"]["objectCount"] < 1:
        raise ValueError("no objects")
    if not s.get("deferred", {}).get("apolloOps"):
        raise ValueError("apolloOps flag missing")


def check_object_sets():
    r = req("POST", "/v1/object-sets/query", {
        "objectType": "WorkOrder",
        "filters": [{"field": "site", "value": "DC-East"}],
        "pageSize": 5,
    })
    if not r.get("items"):
        raise ValueError("empty items")


def check_run_story():
    r = req("POST", "/v1/demo/run-story", {})
    if not r.get("productionWritten"):
        raise ValueError("not written")
    if r.get("before", {}).get("status") == r.get("after", {}).get("status"):
        raise ValueError("status unchanged")


def check_datasets_builds_dlq():
    ds = req("GET", "/v1/datasets")
    if not ds.get("items"):
        raise ValueError("no datasets (ensure-seed should plant demo)")
    b = req("GET", "/v1/builds")
    if not b.get("items"):
        raise ValueError("no builds")
    d = req("GET", "/v1/dlq")
    if not d.get("items"):
        raise ValueError("no dlq sample")


def check_l1_chain():
    sources = req("GET", "/v1/sources").get("items") or []
    if not sources:
        raise ValueError("no sources")
    src_ids = {s.get("id") for s in sources if s.get("id")}
    syncs = req("GET", "/v1/syncs").get("items") or []
    sync_linked = [s for s in syncs if s.get("sourceId") in src_ids]
    if not sync_linked:
        raise ValueError("no sync linked to demo source")
    pipes = req("GET", "/v1/pipelines").get("items") or []
    pipe_linked = [p for p in pipes if p.get("sourceId") in src_ids]
    if not pipe_linked:
        raise ValueError("no pipeline linked to demo source")


def check_governance():
    g = req("GET", "/v1/demo/governance")
    redacted = (g.get("asPublicViewer") or {}).get("redactedFields") or []
    if "internalCost" not in redacted:
        raise ValueError("expected internalCost redacted")
    if (g.get("markingForbidden") or {}).get("code") != "FORBIDDEN":
        raise ValueError("expected FORBIDDEN")


def check_run_capability():
    c = req("POST", "/v1/demo/run-capability", {})
    if not (c.get("job") or {}).get("mediaRid"):
        raise ValueError("no capability mediaRid")
    if not (c.get("parser") or {}).get("ok"):
        raise ValueError("parser extract failed")


def check_run_analytics_story():
    a = req("POST", "/v1/demo/run-analytics-story", {})
    if not a.get("ok"):
        raise ValueError("analytics story not ok")
    if not a.get("productionWritten"):
        raise ValueError("not written")
    if not a.get("draftId"):
        raise ValueError("no draftId")
    if not a.get("lineageId"):
        raise ValueError("no lineageId")
    if int((a.get("read") or {}).get("total") or 0) < 1:
        raise ValueError("read.total < 1")
    if (a.get("before") or {}).get("status") == (a.get("after") or {}).get("status"):
        raise ValueError("status unchanged")
    if not (a.get("exportProbePublic") or {}).get("expected"):
        raise ValueError("export probe should expect FORBIDDEN")


print("=== TB demo smoke ===")

ok("health", lambda: req("GET", "/v1/health"))
ok("ensure-seed", lambda: req("POST", "/v1/demo/ensure-seed", {}))
ok("story", check_story)
ok("object-sets", check_object_sets)
ok("run-story", check_run_story)
ok("datasets-builds-dlq", check_datasets_builds_dlq)
ok("l1-chain", check_l1_chain)
ok("funnel", lambda: req("GET", "/v1/funnel/WorkOrder/status"))
ok("buddy", lambda: req("POST", "/v1/buddy/ask", {
    "query": "WorkOrder risk for wo-1001?",
    "context": {"objectType": "WorkOrder", "objectId": "wo-1001"},
}))
ok("governance", check_governance)
ok("run-capability", check_run_capability)
ok("run-analytics-story", check_run_analytics_story)
ok("modules", lambda: req("GET", "/v1/modules"))

print()
if fail:
    print(f"RESULT: DEMO SMOKE FAIL ({fail})")
    sys.exit(1)
print("RESULT: DEMO SMOKE OK")
PY
