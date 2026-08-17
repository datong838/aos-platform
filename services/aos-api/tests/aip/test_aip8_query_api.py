from datetime import UTC, datetime, timedelta
from uuid import uuid4


def _headers(auth_headers: dict[str, str], key: str | None = None) -> dict[str, str]:
    result = {**auth_headers, "X-Org-Id": "org-org", "X-Project-Id": "dev-project"}
    if key:
        result["Idempotency-Key"] = key
    return result


def test_query_job_http_create_read_start(client, auth_headers) -> None:
    now = datetime.now(UTC)
    body = {"query": {"kind": "semantic", "objectType": "Order", "cutoffAt": now.isoformat()}, "deadlineAt": (now + timedelta(hours=1)).isoformat()}
    missing = client.post("/v1/aip/analyst/query-jobs", headers=_headers(auth_headers), json=body)
    assert missing.status_code == 400
    created = client.post("/v1/aip/analyst/query-jobs", headers=_headers(auth_headers, uuid4().hex), json=body)
    assert created.status_code == 200, created.text
    query_id = created.json()["queryId"]
    assert created.json()["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
    read = client.get(f"/v1/aip/analyst/query-jobs/{query_id}", headers=_headers(auth_headers))
    assert read.status_code == 200 and read.json()["status"] == "queued"
    started = client.post(f"/v1/aip/analyst/query-jobs/{query_id}/start", headers=_headers(auth_headers, uuid4().hex), json={"expectedSequence": 1, "reasonCode": "EXECUTOR_ACCEPTED"})
    assert started.status_code == 200 and started.json()["status"] == "running"
