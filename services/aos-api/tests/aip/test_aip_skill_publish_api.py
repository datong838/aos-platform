"""API tests for skill list + publish-evaluated endpoints."""
from __future__ import annotations

from aos_api.db import connect


def _headers(org_id: str, *, key: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": org_id,
        "X-Project-Id": "dev-project",
    }
    if key:
        headers["Idempotency-Key"] = key
    return headers


def test_list_skills_returns_tenant_envelope(client) -> None:
    response = client.get("/v1/aip/skills", headers=_headers("org-org"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert "items" in body and "count" in body
    assert body["count"] == len(body["items"])


def test_publish_evaluated_rejects_mismatched_idempotency(client) -> None:
    response = client.post(
        "/v1/aip/skills/publish-evaluated",
        headers=_headers("org-org", key="header-key-1"),
        json={
            "sourceSkill": {
                "assetType": "SkillTemplate",
                "assetId": "missing.skill",
                "revision": 1,
                "contentHash": "a" * 64,
            },
            "publicationId": "pub-1",
            "releaseGateDecisionId": "gate-1",
            "modelRouteRef": {
                "assetType": "ModelRouteRevision",
                "assetId": "route-1",
                "revision": 1,
                "contentHash": "b" * 64,
            },
            "runtimePolicyRef": {
                "assetType": "RuntimePolicyRevision",
                "assetId": "policy-1",
                "revision": 1,
                "contentHash": "c" * 64,
            },
            "logicRevisionRef": {
                "assetType": "LogicRevision",
                "assetId": "logic-1",
                "revision": 1,
                "contentHash": "d" * 64,
            },
            "idempotencyKey": "body-key-different",
        },
    )
    assert response.status_code == 400
    assert "Idempotency-Key" in response.json().get("message", "") or "idempotency" in response.text.lower()
