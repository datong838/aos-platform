"""HTTP adversarial checks that must fail before any control service call."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.auth import Principal, require_principal
from aos_api.errors import register_exception_handlers
from aos_api.routers import bundle_compositions, bundle_installations

INSTALLATION_ID = "22222222-2222-4222-8222-222222222222"
COMPOSITION_BODY = {
    "requested": [{"publisher": "aos", "id": "solution.example", "version": "1.0.0"}],
    "platformApiVersion": "1.7.0",
    "platformRelease": "aos-platform/1.7.0",
    "environment": "dev",
}


class FailIfCalled:
    def __init__(self) -> None:
        self.calls = 0

    def __getattr__(self, _name):
        def fail(**_kwargs):
            self.calls += 1
            raise AssertionError("control service must not be called")

        return fail


def _client(service: FailIfCalled) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(bundle_compositions.router)
    app.include_router(bundle_installations.router)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="user:test",
        org_id="org-a",
        project_id="project-a",
        roles=["asset-installer"],
        markings=["public"],
    )
    app.dependency_overrides[bundle_compositions.get_composition_service] = lambda: (
        service
    )
    app.dependency_overrides[bundle_installations.get_installation_service] = lambda: (
        service
    )
    return TestClient(app, raise_server_exceptions=False)


def test_invalid_idempotency_shapes_never_reach_service() -> None:
    service = FailIfCalled()
    invalid_headers = [
        [],
        [("Idempotency-Key", "")],
        [("Idempotency-Key", " padded ")],
        [("Idempotency-Key", "x" * 161)],
        [("Idempotency-Key", "one"), ("Idempotency-Key", "two")],
    ]
    with _client(service) as client:
        responses = [
            client.post(
                "/v1/bundle-compositions:resolve",
                json=COMPOSITION_BODY,
                headers=headers,
            )
            for headers in invalid_headers
        ]

    assert [response.status_code for response in responses] == [400] * len(responses)
    assert {response.json()["code"] for response in responses} == {
        "IDEMPOTENCY_KEY_REQUIRED"
    }
    assert service.calls == 0


def test_invalid_if_match_shapes_never_reach_service() -> None:
    service = FailIfCalled()
    values = [
        None,
        "*",
        'W/"1"',
        "1",
        '"0"',
        '"01"',
        '"9223372036854775808"',
        '"999999999999999999999999999999999999999999"',
    ]
    with _client(service) as client:
        responses = []
        for index, value in enumerate(values):
            headers = [("Idempotency-Key", f"submit-{index}")]
            if value is not None:
                headers.append(("If-Match", value))
            responses.append(
                client.post(
                    f"/v1/bundle-installations/{INSTALLATION_ID}/submit",
                    json={},
                    headers=headers,
                )
            )

    assert responses[0].status_code == 428
    assert responses[0].json()["code"] == "PRECONDITION_REQUIRED"
    assert all(response.status_code == 400 for response in responses[1:])
    assert {response.json()["code"] for response in responses[1:]} == {
        "PRECONDITION_INVALID"
    }
    assert service.calls == 0


def test_strict_empty_action_body_rejects_client_evidence() -> None:
    service = FailIfCalled()
    with _client(service) as client:
        response = client.post(
            f"/v1/bundle-installations/{INSTALLATION_ID}/apply",
            json={"evidenceHash": "client-controlled"},
            headers={"Idempotency-Key": "apply-1", "If-Match": '"1"'},
        )

    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"
    assert service.calls == 0
