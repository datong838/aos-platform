from __future__ import annotations

import uuid

from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("dev-org", "dev-project")
HASH = "a" * 64


def _headers(key: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": SCOPE.org_id,
        "X-Project-Id": SCOPE.project_id,
    }
    if key:
        headers["Idempotency-Key"] = key
    return headers


def _exact(resource_type: str, resource_id: str) -> dict[str, object]:
    return {
        "resourceType": resource_type,
        "resourceId": resource_id,
        "revision": 1,
        "contentHash": HASH,
    }


def _schema(identifier: str) -> dict[str, object]:
    return {
        "resourceType": "Schema",
        "resourceId": identifier,
        "revision": "1",
        "authority": "aip",
    }


def _seed_eval_suite(suite_id: str) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO aip_eval_suite_revision
            (org_id,project_id,suite_id,revision,content_hash,target_ref,dataset_ref,
             judge_ref,cases,gate_threshold,actor)
            VALUES(%s,%s,%s,1,%s,'{}','{}','{}','[{}]',1.0,'test')""",
            (*SCOPE.key, suite_id, HASH),
        )
        conn.commit()


def _eval_payload(suite_id: str) -> dict[str, object]:
    return {
        "suiteRef": _exact("EvalSuiteRevision", suite_id),
        "artifactSchemaRef": _schema("artifact-w2b-api"),
        "severityThresholds": {"critical": 1.0},
        "gatePolicy": {"mode": "all"},
        "returnMapping": {"critical": "draft"},
        "overridePolicy": {"allowed": False},
    }


def _responsibility_payload() -> dict[str, object]:
    return {
        "profile": "ecommerce-standard",
        "templateRef": _exact(
            "ResponsibilityTemplateRevision", "ecommerce-standard"
        ),
        "slots": [
            {
                "slotId": "content.review",
                "responsibilityType": "independent_review",
                "requiredCapabilityIds": ["capability.content.review"],
                "inputSchemaRef": _schema("content.review.input"),
                "outputSchemaRef": _schema("content.review.output"),
                "returnStage": "draft",
                "assignee": {
                    "kind": "agent_instance",
                    "resourceId": "agent-content",
                    "version": 1,
                },
            }
        ],
    }


def test_eval_contract_api_create_replay_list_get_and_blocked_freeze(client) -> None:
    suite_id = f"suite-api-{uuid.uuid4().hex}"
    _seed_eval_suite(suite_id)
    key = f"eval-api-{uuid.uuid4().hex}"
    response = client.post(
        "/v1/aip/production-contracts/eval-contracts",
        headers=_headers(key),
        json=_eval_payload(suite_id),
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["tenant"] == {"orgId": "dev-org", "projectId": "dev-project"}
    assert created["readiness"] == "blocked"
    assert {item["code"] for item in created["blockers"]} == {
        "EVAL_PUBLICATION_MISSING",
        "EVAL_GATE_MISSING",
    }
    replay = client.post(
        "/v1/aip/production-contracts/eval-contracts",
        headers=_headers(key),
        json=_eval_payload(suite_id),
    )
    assert replay.status_code == 201
    assert replay.json()["contractId"] == created["contractId"]
    listing = client.get(
        "/v1/aip/production-contracts/eval-contracts", headers=_headers()
    )
    assert listing.status_code == 200
    assert any(
        item["contractId"] == created["contractId"]
        for item in listing.json()["items"]
    )
    detail = client.get(
        f"/v1/aip/production-contracts/eval-contracts/{created['contractId']}",
        headers=_headers(),
    )
    assert detail.status_code == 200
    frozen = client.post(
        f"/v1/aip/production-contracts/eval-contracts/{created['contractId']}/freeze",
        headers=_headers(f"freeze-{uuid.uuid4().hex}"),
        json={"expectedVersion": created["version"]},
    )
    assert frozen.status_code == 422
    assert frozen.json()["code"] == "AIP_DEPENDENCY_BLOCKED"


def test_eval_contract_api_dependency_drift_and_idempotency_header(client) -> None:
    missing = client.post(
        "/v1/aip/production-contracts/eval-contracts",
        headers=_headers(f"missing-{uuid.uuid4().hex}"),
        json=_eval_payload(f"missing-{uuid.uuid4().hex}"),
    )
    assert missing.status_code == 422
    assert missing.json()["message"] == "EVAL_SUITE_MISSING"
    no_key = client.post(
        "/v1/aip/production-contracts/eval-contracts",
        headers=_headers(),
        json=_eval_payload("missing"),
    )
    assert no_key.status_code == 400
    assert no_key.json()["code"] == "VALIDATION"


def test_responsibility_plan_api_fails_closed_without_installed_template(client) -> None:
    before = client.get(
        "/v1/aip/production-contracts/responsibility-plans", headers=_headers()
    )
    assert before.status_code == 200
    response = client.post(
        "/v1/aip/production-contracts/responsibility-plans",
        headers=_headers(f"plan-{uuid.uuid4().hex}"),
        json=_responsibility_payload(),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "AIP_DEPENDENCY_BLOCKED"
    assert response.json()["message"] == "RESPONSIBILITY_TEMPLATE_MISSING_OR_DRIFTED"
    listing = client.get(
        "/v1/aip/production-contracts/responsibility-plans", headers=_headers()
    )
    assert listing.status_code == 200
    assert listing.json()["count"] == before.json()["count"]


def test_w2b_openapi_contains_all_canonical_routes(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    required = {
        "/v1/aip/production-contracts/eval-contracts",
        "/v1/aip/production-contracts/eval-contracts/{contract_id}",
        "/v1/aip/production-contracts/eval-contracts/{contract_id}/revisions",
        "/v1/aip/production-contracts/eval-contracts/{contract_id}/freeze",
        "/v1/aip/production-contracts/responsibility-plans",
        "/v1/aip/production-contracts/responsibility-plans/{plan_id}",
        "/v1/aip/production-contracts/responsibility-plans/{plan_id}/revisions",
        "/v1/aip/production-contracts/responsibility-plans/{plan_id}/freeze",
    }
    assert required <= set(paths)
