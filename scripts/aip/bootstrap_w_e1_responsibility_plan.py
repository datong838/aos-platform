#!/usr/bin/env python3
"""Bootstrap W-E1 ResponsibilityPlan draft for org-org/dev-project.

Uses Bundle allowlist ResponsibilityTemplate authority + live AgentInstance exact version.
Does not freeze if readiness blocked (bindings/coverage); draft existence clears「尚无」.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/aos-api"))

from aos_api.aip_responsibility_template_authority import published_template_ref  # noqa: E402

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
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    agents = _req("GET", "/agents")
    officer = next(
        item
        for item in agents["items"]
        if item["instanceId"] == "ecommerce.content_officer.default"
    )
    template = published_template_ref("ecommerce-standard")
    payload = {
        "profile": "ecommerce-standard",
        "templateRef": {
            "resourceType": template.resource_type,
            "resourceId": template.resource_id,
            "revision": template.revision,
            "contentHash": template.content_hash,
        },
        "slots": [
            {
                "slotId": "content.review",
                "responsibilityType": "independent_review",
                "requiredCapabilityIds": ["content.review"],
                "inputSchemaRef": {
                    "resourceType": "Schema",
                    "resourceId": "content.review.input",
                    "revision": "1",
                    "authority": "aip",
                },
                "outputSchemaRef": {
                    "resourceType": "Schema",
                    "resourceId": "content.review.output",
                    "revision": "1",
                    "authority": "aip",
                },
                "returnStage": "draft",
                "assignee": {
                    "kind": "agent_instance",
                    "resourceId": officer["instanceId"],
                    "version": int(officer["version"]),
                },
            }
        ],
    }
    created = _req(
        "POST",
        "/production-contracts/responsibility-plans",
        body=payload,
        key="w-e1-bootstrap-responsibility-plan-v1",
    )
    listed = _req("GET", "/production-contracts/responsibility-plans")
    out = {
        "createdPlanId": created.get("planId"),
        "lifecycle": created.get("lifecycle"),
        "readiness": created.get("readiness"),
        "listCount": listed.get("count"),
        "templateHash": template.content_hash,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if listed.get("count", 0) >= 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
