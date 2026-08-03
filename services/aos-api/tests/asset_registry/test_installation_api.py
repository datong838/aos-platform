"""HTTP contract tests for canonical installation endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import ANY

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.asset_registry.composition_contracts import (
    InstallationListResponse,
    InstallationResponse,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import register_exception_handlers
from aos_api.routers import bundle_installations

INSTALLATION_ID = "22222222-2222-4222-8222-222222222222"
COMPOSITION_ID = "11111111-1111-4111-8111-111111111111"
SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
SHA_D = "sha256:" + "d" * 64


def _installation() -> InstallationResponse:
    created_at = datetime(2026, 8, 3, tzinfo=UTC)
    return InstallationResponse.model_validate(
        {
            "installationId": INSTALLATION_ID,
            "displayName": "Example installation",
            "state": "draft",
            "currentRevision": 1,
            "activeRevision": None,
            "previousActiveRevision": None,
            "etagVersion": 1,
            "createdAt": created_at,
            "updatedAt": created_at,
            "current": {
                "installationId": INSTALLATION_ID,
                "revision": 1,
                "parentRevision": None,
                "state": "draft",
                "compositionId": COMPOSITION_ID,
                "lockRevision": 1,
                "lockHash": SHA_A,
                "permissionDiffHash": SHA_B,
                "migrationPlanHash": SHA_C,
                "contributionDiffHash": SHA_D,
                "overlayRevision": "overlay-v1",
                "requestedBy": "user:test",
                "decisionId": None,
                "createdAt": created_at,
            },
            "decision": None,
            "events": [
                {
                    "sequence": 1,
                    "fromRevision": None,
                    "toRevision": 1,
                    "fromState": None,
                    "toState": "draft",
                    "actor": "user:test",
                    "reason": None,
                    "evidence": None,
                    "createdAt": created_at,
                }
            ],
        }
    )


class FakeService:
    def __init__(self) -> None:
        self.calls = []
        self.installation = _installation()

    def _command(self, operation, **kwargs):
        self.calls.append((operation, kwargs))
        return SimpleNamespace(
            response_json=self.installation.model_dump(mode="json", by_alias=True),
            response_etag='"1"',
        )

    def create(self, **kwargs):
        return self._command("create", **kwargs)

    def list(self, **kwargs):
        self.calls.append(("list", kwargs))
        return InstallationListResponse(
            items=[self.installation], total=1, limit=50, offset=0
        )

    def get(self, **kwargs):
        self.calls.append(("get", kwargs))
        return self.installation

    def __getattr__(self, name):
        if name in {"submit", "approve", "reject", "apply", "verify", "rollback"}:
            return lambda **kwargs: self._command(name, **kwargs)
        raise AttributeError(name)


def _client(service: FakeService) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(bundle_installations.router)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="user:test",
        org_id="org-a",
        project_id="project-a",
        roles=["asset-installer"],
        markings=["public"],
    )
    app.dependency_overrides[bundle_installations.get_installation_service] = lambda: (
        service
    )
    return TestClient(app, raise_server_exceptions=False)


def test_create_list_and_get_preserve_etag_contract() -> None:
    service = FakeService()
    with _client(service) as client:
        created = client.post(
            "/v1/bundle-installations",
            json={
                "compositionId": COMPOSITION_ID,
                "lockRevision": 1,
                "overlayRevision": "overlay-v1",
                "displayName": "Example installation",
            },
            headers={"Idempotency-Key": "create-1"},
        )
        listed = client.get("/v1/bundle-installations")
        fetched = client.get(f"/v1/bundle-installations/{INSTALLATION_ID}")

    assert created.status_code == 201
    assert listed.status_code == fetched.status_code == 200
    assert created.headers["etag"] == fetched.headers["etag"] == '"1"'
    assert created.json()["etagVersion"] == fetched.json()["etagVersion"] == 1


@pytest.mark.parametrize(
    ("action", "body"),
    [
        ("submit", {}),
        (
            "approve",
            {
                "lockHash": SHA_A,
                "permissionDiffHash": SHA_B,
                "migrationPlanHash": SHA_C,
                "contributionDiffHash": SHA_D,
            },
        ),
        ("reject", {"reason": "not approved"}),
        ("apply", {}),
        ("verify", {}),
        ("rollback", {"reason": "verification regression"}),
    ],
)
def test_all_actions_delegate_exact_headers(action: str, body: dict) -> None:
    service = FakeService()
    with _client(service) as client:
        response = client.post(
            f"/v1/bundle-installations/{INSTALLATION_ID}/{action}",
            json=body,
            headers={"Idempotency-Key": f"{action}-1", "If-Match": '"1"'},
        )

    assert response.status_code == 200
    assert response.headers["etag"] == '"1"'
    assert service.calls == [
        (
            action,
            {
                "installation_id": INSTALLATION_ID,
                "request": ANY,
                "org_id": "org-a",
                "project_id": "project-a",
                "actor": "user:test",
                "roles": ["asset-installer"],
                "markings": ["public"],
                "idempotency_key": f"{action}-1",
                "if_match": '"1"',
            },
        )
    ]


def test_action_header_failures_happen_before_service_call() -> None:
    service = FakeService()
    with _client(service) as client:
        missing_if_match = client.post(
            f"/v1/bundle-installations/{INSTALLATION_ID}/submit",
            json={},
            headers={"Idempotency-Key": "submit-1"},
        )
        duplicate_if_match = client.post(
            f"/v1/bundle-installations/{INSTALLATION_ID}/submit",
            json={},
            headers=[
                ("Idempotency-Key", "submit-2"),
                ("If-Match", '"1"'),
                ("If-Match", '"2"'),
            ],
        )

    assert missing_if_match.status_code == 428
    assert missing_if_match.json()["code"] == "PRECONDITION_REQUIRED"
    assert duplicate_if_match.status_code == 400
    assert duplicate_if_match.json()["code"] == "PRECONDITION_INVALID"
    assert service.calls == []
