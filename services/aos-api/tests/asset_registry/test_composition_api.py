"""HTTP contract tests for canonical composition endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import (
    CompositionLockPayload,
    CompositionRequest,
    StoredCompositionLock,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import register_exception_handlers
from aos_api.routers import bundle_compositions

COMPOSITION_ID = "11111111-1111-4111-8111-111111111111"
SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64


def _request() -> CompositionRequest:
    return CompositionRequest.model_validate(
        {
            "requested": [
                {"publisher": "aos", "id": "solution.example", "version": "1.0.0"}
            ],
            "platformApiVersion": "1.7.0",
            "platformRelease": "aos-platform/1.7.0",
            "environment": "dev",
        }
    )


def _lock() -> StoredCompositionLock:
    empty_permissions = {
        "roles": [],
        "markings": [],
        "dataScopes": [],
        "actionTypes": [],
    }
    payload = CompositionLockPayload.model_validate(
        {
            "lockSchemaVersion": "aos.dev/composition-lock/v1alpha1",
            "resolverVersion": "aos-resolver/1.0.0",
            "request": _request().lock_request(),
            "registrySnapshotHash": SHA_A,
            "resolved": [
                {
                    "publisher": "aos",
                    "id": "solution.example",
                    "version": "1.0.0",
                    "kind": "SolutionPack",
                    "contentHash": SHA_A,
                    "signatureFingerprint": SHA_B,
                    "releaseEvidenceRevision": SHA_C,
                    "dependencies": [],
                    "optionalDependencies": [],
                    "conflicts": [],
                    "capabilities": {"provides": [], "requires": []},
                    "permissions": empty_permissions,
                    "migration": {
                        "planRef": None,
                        "downgradePolicy": "retain-canonical",
                    },
                    "contributions": [],
                    "selectionReason": "requested",
                }
            ],
            "edges": [],
            "capabilityProviders": [],
            "permissionDiff": {
                "baseline": empty_permissions,
                "target": empty_permissions,
                "added": empty_permissions,
                "removed": empty_permissions,
                "unchanged": empty_permissions,
            },
            "migrationPlan": {
                "baseline": [],
                "target": [],
                "added": [],
                "removed": [],
                "changed": [],
            },
            "contributionDiff": {
                "baseline": [],
                "target": [],
                "added": [],
                "removed": [],
                "unchanged": [],
            },
            "currentInstallationRef": None,
        }
    )
    return StoredCompositionLock.model_validate(
        {
            "compositionId": COMPOSITION_ID,
            "revision": 1,
            "payload": payload,
            "lockHash": canonical_sha256(payload.hash_payload_dump()),
            "permissionDiffHash": canonical_sha256(
                payload.permission_diff.model_dump(mode="json", by_alias=True)
            ),
            "migrationPlanHash": canonical_sha256(
                payload.migration_plan.model_dump(mode="json", by_alias=True)
            ),
            "contributionDiffHash": canonical_sha256(
                payload.contribution_diff.model_dump(mode="json", by_alias=True)
            ),
            "createdAt": datetime(2026, 8, 3, tzinfo=UTC),
        }
    )


class FakeService:
    def __init__(self) -> None:
        self.calls = []
        self.lock = _lock()

    def resolve(self, **kwargs):
        self.calls.append(("resolve", kwargs))
        return SimpleNamespace(
            response_json=self.lock.model_dump(mode="json", by_alias=True)
        )

    def get_lock(self, **kwargs):
        self.calls.append(("get_lock", kwargs))
        return self.lock


def _client(service: FakeService) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(bundle_compositions.router)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="user:test",
        org_id="org-a",
        project_id="project-a",
        roles=["developer"],
        markings=["public"],
    )
    app.dependency_overrides[bundle_compositions.get_composition_service] = lambda: (
        service
    )
    return TestClient(app, raise_server_exceptions=False)


def test_resolve_requires_exactly_one_raw_idempotency_header() -> None:
    service = FakeService()
    with _client(service) as client:
        missing = client.post(
            "/v1/bundle-compositions:resolve",
            json=_request().model_dump(mode="json", by_alias=True),
        )
        duplicate = client.post(
            "/v1/bundle-compositions:resolve",
            json=_request().model_dump(mode="json", by_alias=True),
            headers=[("Idempotency-Key", "one"), ("Idempotency-Key", "two")],
        )

    assert missing.status_code == duplicate.status_code == 400
    assert (
        missing.json()["code"] == duplicate.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"
    )
    assert service.calls == []


def test_composition_routes_delegate_with_principal_and_stable_schema() -> None:
    service = FakeService()
    with _client(service) as client:
        resolved = client.post(
            "/v1/bundle-compositions:resolve",
            json=_request().model_dump(mode="json", by_alias=True),
            headers={"Idempotency-Key": "resolve-1"},
        )
        fetched = client.get(f"/v1/bundle-compositions/{COMPOSITION_ID}/locks/1")
        schema = client.app.openapi()

    assert resolved.status_code == 201
    assert fetched.status_code == 200
    assert "etag" not in {key.lower() for key in resolved.headers}
    assert service.calls[0][1]["org_id"] == "org-a"
    operation_ids = {
        operation["operationId"]
        for path in schema["paths"].values()
        for operation in path.values()
    }
    assert operation_ids == {
        "resolve_bundle_composition",
        "get_bundle_composition_lock",
    }
    assert schema["paths"]["/v1/bundle-compositions:resolve"]["post"]["security"]
