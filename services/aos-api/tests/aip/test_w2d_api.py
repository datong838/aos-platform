from __future__ import annotations

import uuid

from test_w2d_start_gate import _runtime_counts, _seed_start_candidate
from test_w2d_store import _seed


def _headers(key: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def test_w2d_impact_preview_api_uses_principal_tenant_and_reads_back(client) -> None:
    request, _ = _seed()
    response = client.post(
        "/v1/aip/production-contracts/impact-previews",
        headers=_headers(f"preview-api-{uuid.uuid4().hex}"),
        json=request.model_dump(mode="json", by_alias=True),
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["tenant"] == {"orgId": "dev-org", "projectId": "dev-project"}
    detail = client.get(
        f"/v1/aip/production-contracts/impact-previews/{created['previewId']}",
        headers=_headers(),
    )
    assert detail.status_code == 200
    assert detail.json()["contentHash"] == created["contentHash"]
    listing = client.get(
        "/v1/aip/production-contracts/impact-previews", headers=_headers()
    )
    assert listing.status_code == 200
    assert any(
        item["previewId"] == created["previewId"]
        for item in listing.json()["items"]
    )


def test_w2d_start_api_returns_machine_readable_blocked_without_runtime(client) -> None:
    request, _ = _seed_start_candidate()
    before = _runtime_counts(request.task_id)
    response = client.post(
        "/v1/aip/production-contracts/production-runs/start",
        headers=_headers(f"start-api-{uuid.uuid4().hex}"),
        json=request.model_dump(mode="json", by_alias=True),
    )
    assert response.status_code == 200, response.text
    decision = response.json()
    assert decision["status"] == "blocked"
    assert decision["taskRunRef"] is None
    assert decision["blockers"]
    assert _runtime_counts(request.task_id) == before
    detail = client.get(
        "/v1/aip/production-contracts/production-start-decisions/"
        f"{decision['decisionId']}",
        headers=_headers(),
    )
    assert detail.status_code == 200
    assert detail.json()["decisionId"] == decision["decisionId"]

    isolated = client.post(
        "/v1/aip/production-contracts/production-runs/start",
        headers={
            "Authorization": "Bearer dev",
            "X-Org-Id": "other-org",
            "X-Project-Id": "dev-project",
            "Idempotency-Key": f"isolated-{uuid.uuid4().hex}",
        },
        json=request.model_dump(mode="json", by_alias=True),
    )
    assert isolated.status_code == 404


def test_w2d_mutation_requires_idempotency_key_and_openapi_is_frozen(client) -> None:
    request, _ = _seed_start_candidate()
    missing_key = client.post(
        "/v1/aip/production-contracts/production-runs/start",
        headers=_headers(),
        json=request.model_dump(mode="json", by_alias=True),
    )
    assert missing_key.status_code == 400
    assert missing_key.json()["code"] == "VALIDATION"
    paths = client.get("/openapi.json").json()["paths"]
    required = {
        "/v1/aip/production-contracts/impact-previews",
        "/v1/aip/production-contracts/impact-previews/{preview_id}",
        "/v1/aip/production-contracts/impact-previews/{preview_id}/revisions",
        "/v1/aip/production-contracts/impact-previews/{preview_id}/freeze",
        "/v1/aip/production-contracts/production-contexts/freeze",
        "/v1/aip/production-contracts/production-contexts",
        "/v1/aip/production-contracts/production-contexts/{context_id}",
        "/v1/aip/production-contracts/production-runs/start",
        "/v1/aip/production-contracts/production-start-decisions",
        "/v1/aip/production-contracts/production-start-decisions/{decision_id}",
    }
    assert required <= set(paths)
