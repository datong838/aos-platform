#!/usr/bin/env python3
"""Bootstrap W-E2 StageTemplate draft for org-org/dev-project."""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/aos-api"))

from aos_api.aip_stage_template_authority import published_source_bundle_ref  # noqa: E402

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
    source = published_source_bundle_ref()
    payload = {
        "profile": "ecommerce-standard",
        "sourceBundleRef": {
            "resourceType": source.resource_type,
            "resourceId": source.resource_id,
            "revision": source.revision,
            "contentHash": source.content_hash,
        },
        "stages": [
            {
                "stageId": "content.review",
                "title": "内容审核",
                "dependsOn": [],
                "applicability": {"kind": "always", "profiles": []},
                "requiredSlotIds": ["content.review"],
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
            }
        ],
    }
    created = _req(
        "POST",
        "/production-contracts/stage-templates",
        body=payload,
        key="w-e2-bootstrap-stage-template-v1",
    )
    listed = _req("GET", "/production-contracts/stage-templates")
    out = {
        "createdTemplateId": created.get("templateId"),
        "lifecycle": created.get("lifecycle"),
        "readiness": created.get("readiness"),
        "listCount": listed.get("count"),
        "sourceHash": source.content_hash,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if listed.get("count", 0) >= 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
