#!/usr/bin/env python3
"""Bootstrap W-E4 ArtifactRelation + ReviewIssue for org-org/dev-project."""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.request
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
        raise RuntimeError(f"{method} {path} -> {exc.code}: {exc.read().decode()[:1200]}") from exc


def main() -> int:
    scope = TenantScope(ORG, PROJECT)
    with connect(scope) as conn:
        arts = conn.execute(
            """SELECT artifact_id, content_hash FROM aip_artifact
            WHERE org_id=%s AND project_id=%s ORDER BY artifact_id LIMIT 2""",
            scope.key,
        ).fetchall()
        report = conn.execute(
            """SELECT report_id, revision, content_hash FROM aip_eval_report_revision
            WHERE org_id=%s AND project_id=%s ORDER BY created_at DESC NULLS LAST LIMIT 1""",
            scope.key,
        ).fetchone()
        if report is None:
            report = conn.execute(
                """SELECT report_id, revision, content_hash FROM aip_eval_report_revision
                WHERE org_id=%s AND project_id=%s LIMIT 1""",
                scope.key,
            ).fetchone()
    if len(arts) < 2 or not report:
        raise RuntimeError("need >=2 artifacts and 1 eval report revision")

    relation = _req(
        "POST",
        "/production-contracts/artifact-relations",
        body={
            "relationType": "variant_of",
            "fromArtifact": {
                "artifactId": arts[0]["artifact_id"],
                "contentHash": arts[0]["content_hash"],
            },
            "toArtifact": {
                "artifactId": arts[1]["artifact_id"],
                "contentHash": arts[1]["content_hash"],
            },
            "reason": "W-E4 bootstrap: link two sealed pilot artifacts as variants for review desk density",
        },
        key="w-e4-bootstrap-artifact-relation-v1",
    )

    rule_payload = {
        "resourceType": "EvalRuleRevision",
        "resourceId": "ecommerce.review.content.honesty",
        "revision": 1,
        "title": "内容诚实性抽检",
    }
    rule_hash = hashlib.sha256(
        json.dumps(rule_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    issue = _req(
        "POST",
        "/production-contracts/review-issues",
        body={
            "ruleRef": {
                "resourceType": "EvalRuleRevision",
                "resourceId": rule_payload["resourceId"],
                "revision": 1,
                "contentHash": rule_hash,
            },
            "severity": "warning",
            "artifactRef": {
                "artifactId": arts[0]["artifact_id"],
                "contentHash": arts[0]["content_hash"],
            },
            "evalReportRef": {
                "resourceType": "EvalReportRevision",
                "resourceId": report["report_id"],
                "revision": int(report["revision"]),
                "contentHash": report["content_hash"],
            },
            "location": {"path": "output.text", "note": "W-E4 bootstrap location"},
            "evidenceRefs": [],
            "suggestedFix": "核对输出与证据 Bundle exact ref，禁止用摘要冒充事实。",
            "returnStage": "content.review",
        },
        key="w-e4-bootstrap-review-issue-v1",
    )

    relations = _req("GET", "/production-contracts/artifact-relations")
    issues = _req("GET", "/production-contracts/review-issues")
    out = {
        "relationId": relation.get("relationId"),
        "issueId": issue.get("issueId"),
        "relationCount": relations.get("count"),
        "issueCount": issues.get("count"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if relations.get("count", 0) >= 1 and issues.get("count", 0) >= 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
