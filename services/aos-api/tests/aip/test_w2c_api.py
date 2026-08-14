from __future__ import annotations

import uuid


def _headers(key: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def _stage_template_payload() -> dict[str, object]:
    return {
        "profile": "ecommerce-standard",
        "sourceBundleRef": {
            "resourceType": "AssetBundleRevision",
            "resourceId": "vertical.ecommerce.standard",
            "revision": 1,
            "contentHash": "a" * 64,
        },
        "stages": [
            {
                "stageId": "analysis",
                "title": "分析",
                "applicability": {"kind": "always"},
                "requiredSlotIds": ["data-analysis"],
                "inputSchemaRef": {
                    "resourceType": "Schema",
                    "resourceId": "analysis.input",
                    "revision": "1",
                    "authority": "aip",
                },
                "outputSchemaRef": {
                    "resourceType": "Schema",
                    "resourceId": "analysis.output",
                    "revision": "1",
                    "authority": "aip",
                },
            }
        ],
    }


def test_w2c_stage_template_api_create_replay_list_get_and_blocked_freeze(client) -> None:
    key = f"stage-api-{uuid.uuid4().hex}"
    created_response = client.post(
        "/v1/aip/production-contracts/stage-templates",
        headers=_headers(key),
        json=_stage_template_payload(),
    )
    assert created_response.status_code == 201, created_response.text
    created = created_response.json()
    assert created["tenant"] == {"orgId": "dev-org", "projectId": "dev-project"}
    assert created["readiness"] == "blocked"
    assert created["blockers"][0]["code"] == "STAGE_SOURCE_AUTHORITY_UNAVAILABLE"

    replay = client.post(
        "/v1/aip/production-contracts/stage-templates",
        headers=_headers(key),
        json=_stage_template_payload(),
    )
    assert replay.status_code == 201
    assert replay.json()["templateId"] == created["templateId"]

    listing = client.get(
        "/v1/aip/production-contracts/stage-templates", headers=_headers()
    )
    assert listing.status_code == 200
    assert any(
        item["templateId"] == created["templateId"]
        for item in listing.json()["items"]
    )
    detail = client.get(
        f"/v1/aip/production-contracts/stage-templates/{created['templateId']}",
        headers=_headers(),
    )
    assert detail.status_code == 200
    frozen = client.post(
        f"/v1/aip/production-contracts/stage-templates/{created['templateId']}/freeze",
        headers=_headers(f"freeze-{uuid.uuid4().hex}"),
        json={"expectedVersion": created["version"]},
    )
    assert frozen.status_code == 422
    assert frozen.json()["code"] == "AIP_DEPENDENCY_BLOCKED"


def test_w2c_mutation_requires_idempotency_key(client) -> None:
    response = client.post(
        "/v1/aip/production-contracts/stage-templates",
        headers=_headers(),
        json=_stage_template_payload(),
    )
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"


def test_w2c_openapi_contains_all_canonical_routes(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    required = {
        "/v1/aip/production-contracts/stage-templates",
        "/v1/aip/production-contracts/stage-templates/{template_id}",
        "/v1/aip/production-contracts/stage-templates/{template_id}/revisions",
        "/v1/aip/production-contracts/stage-templates/{template_id}/freeze",
        "/v1/aip/production-contracts/stage-templates/{template_id}/compile",
        "/v1/aip/production-contracts/artifact-relations",
        "/v1/aip/production-contracts/review-issues",
        "/v1/aip/production-contracts/review-issues/{issue_id}",
        "/v1/aip/production-contracts/review-issues/{issue_id}/resolve",
        "/v1/aip/production-contracts/review-issues/{issue_id}/return",
    }
    assert required <= set(paths)
