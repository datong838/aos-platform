"""AIP-8 analyst legacy-path regression tests."""
from __future__ import annotations

from datetime import UTC, datetime


def _org_headers(auth_headers: dict[str, str]) -> dict[str, str]:
    return {**auth_headers, "X-Org-Id": "org-org", "X-Project-Id": "dev-project"}


def test_http_rejects_legacy_sql_payload(client, auth_headers):
    response = client.post(
        "/v1/aip/analyst/query",
        headers=_org_headers(auth_headers),
        json={"sql": "SELECT * FROM shops"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"


def test_http_returns_honest_blocked_without_canonical_adapter(client, auth_headers):
    response = client.post(
        "/v1/aip/analyst/query",
        headers=_org_headers(auth_headers),
        json={
            "kind": "semantic",
            "objectType": "Order",
            "cutoffAt": datetime.now(UTC).isoformat(),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert body["status"] == "blocked"
    assert body["rows"] == []
    assert body["sourceRefs"] == []
    assert [item["code"] for item in body["blockers"]] == [
        "SEMANTIC_ADAPTER_UNAVAILABLE"
    ]
