#!/usr/bin/env python3
"""Bootstrap W-E3 ImpactPreview draft for org-org/dev-project from live exact refs."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/aos-api"))

from aos_api.db import connect  # noqa: E402
from aos_api.tenant_scope import TenantScope  # noqa: E402

API = "http://127.0.0.1:8080/v1/aip"
ORG = "org-org"
PROJECT = "dev-project"


def _req(method: str, path: str, *, body: dict | None = None, key: str | None = None) -> dict:
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": ORG,
        "X-Project-Id": PROJECT,
        "Content-Type": "application/json",
    }
    if key:
        headers["Idempotency-Key"] = key
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} -> {exc.code}: {detail[:1200]}") from exc


def _unknown() -> dict:
    return {"quality": "unknown", "value": None, "sourceRefs": [], "details": {}}


def main() -> int:
    briefs = _req("GET", "/production-contracts/task-briefs")["items"]
    bundles = _req("GET", "/production-contracts/evidence-bundles")["items"]
    evals = _req("GET", "/production-contracts/eval-contracts")["items"]
    plans = _req("GET", "/production-contracts/responsibility-plans")["items"]
    stages = _req("GET", "/production-contracts/stage-templates")["items"]

    brief = next(item for item in briefs if item.get("lifecycle") == "frozen")
    bundle = next(
        item
        for item in bundles
        if item.get("lifecycle") == "frozen"
        and (item.get("briefRef") or {}).get("resourceId") == brief["briefId"]
    )
    eval_c = next(item for item in evals if item.get("lifecycle") == "frozen")
    resp = plans[0]
    stage = next(item for item in stages if item.get("lifecycle") == "frozen")
    task_id = brief["taskId"]

    scope = TenantScope(ORG, PROJECT)
    with connect(scope) as conn:
        plan_row = conn.execute(
            """SELECT plan_revision_id, revision, content_hash FROM aip_plan_revision
            WHERE org_id=%s AND project_id=%s AND task_id=%s
            ORDER BY revision DESC LIMIT 1""",
            (*scope.key, task_id),
        ).fetchone()
    if not plan_row:
        raise RuntimeError(f"no plan revision for {task_id}")

    expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    payload = {
        "taskId": task_id,
        "planRef": {
            "resourceType": "PlanRevision",
            "resourceId": plan_row["plan_revision_id"],
            "revision": int(plan_row["revision"]),
            "contentHash": plan_row["content_hash"],
        },
        "briefRef": {
            "resourceType": "TaskBriefRevision",
            "resourceId": brief["briefId"],
            "revision": int(brief["revision"]),
            "contentHash": brief["contentHash"],
        },
        "evidenceBundleRef": {
            "resourceType": "EvidenceBundleRevision",
            "resourceId": bundle["bundleId"],
            "revision": int(bundle["revision"]),
            "contentHash": bundle["contentHash"],
        },
        "evalContractRef": {
            "resourceType": "EvalContractRevision",
            "resourceId": eval_c["contractId"],
            "revision": int(eval_c["revision"]),
            "contentHash": eval_c["contentHash"],
        },
        "responsibilityPlanRef": {
            "resourceType": "ResponsibilityPlanRevision",
            "resourceId": resp["planId"],
            "revision": int(resp["revision"]),
            "contentHash": resp["contentHash"],
        },
        "stageTemplateRef": {
            "resourceType": "StageTemplateRevision",
            "resourceId": stage["templateId"],
            "revision": int(stage["revision"]),
            "contentHash": stage["contentHash"],
        },
        "impact": {
            "objectScope": _unknown(),
            "channelScope": _unknown(),
            "cost": _unknown(),
            "budget": _unknown(),
            "risks": _unknown(),
            "reversibility": _unknown(),
            "approvalChain": _unknown(),
            "rateCapacityKill": _unknown(),
        },
        "expiresAt": expires,
    }
    created = _req(
        "POST",
        "/production-contracts/impact-previews",
        body=payload,
        key="w-e3-bootstrap-impact-preview-v1",
    )
    listed = _req("GET", "/production-contracts/impact-previews")
    out = {
        "previewId": created.get("previewId"),
        "lifecycle": created.get("lifecycle"),
        "readiness": created.get("readiness"),
        "blockerCodes": [b.get("code") for b in created.get("blockers") or []],
        "listCount": listed.get("count"),
        "taskId": task_id,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if listed.get("count", 0) >= 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
