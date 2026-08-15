from __future__ import annotations

from datetime import UTC, datetime

from aos_api.aip_assist_contracts import AssistEventType, AssistStreamEvent
from aos_api.routers.aip_assist_runtime import get_aip_assist_service


def headers(auth_headers: dict[str, str]) -> dict[str, str]:
    return {
        **auth_headers,
        "X-Org-Id": "org-org",
        "X-Project-Id": "dev-project",
        "Idempotency-Key": "p8-4a-api-test",
    }


def body() -> dict:
    now = datetime.now(UTC).isoformat()
    base = {"revision": "1", "authority": "test"}
    return {
        "taskRef": {**base, "resourceType": "Task", "resourceId": "task-1"},
        "taskRunRef": {**base, "resourceType": "TaskRun", "resourceId": "run-1"},
        "agentRunRef": {**base, "resourceType": "AgentRun", "resourceId": "agent-run-1"},
        "cutoffAt": now,
    }


def test_canonical_assist_requires_authentication(client) -> None:
    response = client.post(
        "/v1/aip/assist/threads",
        headers={"Idempotency-Key": "missing-auth"},
        json=body(),
    )
    assert response.status_code == 401


def test_canonical_assist_fails_closed_without_authority(client, auth_headers) -> None:
    response = client.post(
        "/v1/aip/assist/threads",
        headers=headers(auth_headers),
        json=body(),
    )
    assert response.status_code == 503
    assert response.json()["code"] == "ASSIST_AUTHORITY_UNAVAILABLE"


def test_legacy_sample_assist_routes_are_not_mounted(client, auth_headers) -> None:
    request_headers = headers(auth_headers)
    for path in (
        "/v1/aip/assist/welcome",
        "/v1/aip/assist/suggestions",
        "/v1/aip/assist/conversations",
        "/api/aip/assist-context",
        "/api/aip/assist-perms",
    ):
        assert client.get(path, headers=request_headers).status_code == 404


def test_stream_boundary_emits_only_typed_sse(client, auth_headers) -> None:
    now = datetime.now(UTC)

    class FakeService:
        def stream_turn(self, scope, principal, thread_id, request, *, idempotency_key):
            assert scope.key == ("org-org", "dev-project")
            assert principal.subject
            assert request.message == "核查订单风险"
            return [
                AssistStreamEvent(
                    event_type=AssistEventType.START,
                    thread_id=thread_id,
                    turn_id="turn-1",
                    sequence=1,
                    occurred_at=now,
                ),
                AssistStreamEvent(
                    event_type=AssistEventType.DONE,
                    thread_id=thread_id,
                    turn_id="turn-1",
                    sequence=2,
                    occurred_at=now,
                ),
            ]

    client.app.dependency_overrides[get_aip_assist_service] = lambda: FakeService()
    try:
        response = client.post(
            "/v1/aip/assist/threads/thread-1/turns:stream",
            headers=headers(auth_headers),
            json={
                "message": "核查订单风险",
                "expectedThreadVersion": 1,
                "cutoffAt": now.isoformat(),
            },
        )
    finally:
        client.app.dependency_overrides.pop(get_aip_assist_service, None)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: start" in response.text
    assert '"eventType": "done"' in response.text


def test_openapi_exposes_only_canonical_assist_control_boundary(client) -> None:
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    assert "/v1/aip/assist/threads" in paths
    assert "/v1/aip/assist/threads/{thread_id}/turns:stream" in paths
    assert "/v1/aip/assist/chat" not in paths
    assert "/v1/aip/assist/welcome" not in paths
    parameters = paths["/v1/aip/assist/threads"]["post"]["parameters"]
    assert any(
        item["in"] == "header"
        and item["name"] == "Idempotency-Key"
        and item.get("required") is True
        for item in parameters
    )
