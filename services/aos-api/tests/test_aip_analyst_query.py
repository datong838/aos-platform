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


def test_http_fails_closed_when_canonical_object_type_is_unavailable(client, auth_headers):
    response = client.post(
        "/v1/aip/analyst/query",
        headers=_org_headers(auth_headers),
        json={
            "kind": "semantic",
            "objectType": "Order",
            "cutoffAt": datetime.now(UTC).isoformat(),
        },
    )
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
    assert response.json()["message"] == "object type is not installed"
