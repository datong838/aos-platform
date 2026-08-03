"""M4-2 contract tests for the isolated Integration Case HTTP adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.asset_registry.errors import (
    AssetNotFoundError,
    EvidenceIntegrityCorruptError,
    EvidenceReferenceInvalidError,
    IdempotencyConflictError,
    MarkingAccessDeniedError,
    RevisionConflictError,
)
from aos_api.asset_registry.integration_contracts import (
    INTEGRATION_CASE_DETAIL_ADAPTER,
    CurrentIntegrationCaseDetail,
    IntegrationCaseListResponse,
    IntegrationCaseTimelineResponse,
    IntegrationEvidenceSnapshotResponse,
    IntegrationStage,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import register_exception_handlers
from aos_api.routers import integration_cases

CASE_ID = "11111111-1111-4111-8111-111111111111"
INSTALLATION_ID = "22222222-2222-4222-8222-222222222222"
COMPOSITION_ID = "33333333-3333-4333-8333-333333333333"
BLOCKER_ID = "44444444-4444-4444-8444-444444444444"
HASH_A = "sha256:" + "a" * 64
NOW = datetime(2026, 8, 4, tzinfo=UTC)
ALL_ROLES = ["integration-case-reader", "integration-case-maker", "integration-case-projector"]


@pytest.fixture(autouse=True)
def _service_context_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        integration_cases,
        "build_integration_request_context",
        lambda principal: SimpleNamespace(
            org_id=principal.org_id,
            project_id=principal.project_id,
            subject=principal.subject,
            roles=tuple(principal.roles),
            markings=tuple(principal.markings),
        ),
    )


def _gates() -> list[dict[str, Any]]:
    return [
        {
            "stage": stage.value,
            "status": "satisfied" if stage == IntegrationStage.PLANNED else "not_evaluated",
            "evidenceRefs": [HASH_A] if stage == IntegrationStage.PLANNED else [],
            "reasonRefs": [],
        }
        for stage in IntegrationStage
    ]


def _metric(value: int | None, aggregation: str = "count") -> dict[str, Any]:
    return {
        "value": value,
        "aggregation": aggregation,
        "measuredCaseCount": 0 if value is None else 1,
        "eligibleCaseCount": 1,
        "cutoffAt": NOW,
    }


def _detail() -> CurrentIntegrationCaseDetail:
    return INTEGRATION_CASE_DETAIL_ADAPTER.validate_python(
        {
            "caseId": CASE_ID,
            "scope": "current",
            "displayName": "Integration case",
            "owner": "subject:owner-001",
            "installationId": INSTALLATION_ID,
            "installationRevision": 5,
            "overlayRevision": "overlay-v1",
            "compositionId": COMPOSITION_ID,
            "lockRevision": 2,
            "lockHash": HASH_A,
            "computedStage": "planned",
            "snapshotRevision": 1,
            "cutoffAt": NOW,
            "blockerCount": 0,
            "etagVersion": 1,
            "createdAt": NOW,
            "updatedAt": NOW,
            "stageGates": _gates(),
            "latestEvidence": [],
            "blockers": [],
            "nextProjectionAt": None,
            "metrics": {
                "connectorCount": _metric(None, "distinct_count"),
                "pipelineCount": _metric(None, "distinct_count"),
                "datasetRowCount": _metric(0, "sum"),
                "latencyMs": _metric(None, "max"),
            },
        }
    )


def _list_response() -> IntegrationCaseListResponse:
    detail = _detail()
    item = {
        key: value
        for key, value in detail.model_dump(mode="python", by_alias=True).items()
        if key
        in {
            "caseId", "scope", "displayName", "owner", "installationId",
            "overlayRevision", "computedStage", "snapshotRevision", "cutoffAt",
            "blockerCount", "etagVersion", "createdAt", "updatedAt",
        }
    }
    metrics = detail.metrics.model_dump(mode="python", by_alias=True)
    return IntegrationCaseListResponse.model_validate(
        {
            "scope": "current",
            "items": [item],
            "total": 1,
            "limit": 50,
            "offset": 0,
            "stats": {
                **metrics,
                "caseCount": _metric(1),
                "productionActiveCount": _metric(0),
            },
        }
    )


def _snapshot() -> IntegrationEvidenceSnapshotResponse:
    return IntegrationEvidenceSnapshotResponse.model_validate(
        {
            "caseId": CASE_ID,
            "instanceRevision": 1,
            "snapshotRevision": 1,
            "snapshotHash": HASH_A,
            "stagePolicyVersion": "aos.integration-stage/v1",
            "computedStage": "planned",
            "stageGates": _gates(),
            "blockerRefs": [],
            "cutoffAt": NOW,
            "nextProjectionAt": None,
            "evidenceCount": 0,
            "etagVersion": 1,
            "createdAt": NOW,
        }
    )


def _timeline() -> IntegrationCaseTimelineResponse:
    return IntegrationCaseTimelineResponse.model_validate(
        {
            "caseId": CASE_ID,
            "scope": "current",
            "items": [
                {
                    "sequence": 1,
                    "snapshotRevision": 1,
                    "oldStage": None,
                    "newStage": "planned",
                    "cause": "created",
                    "reasonRefs": [HASH_A],
                    "createdAt": NOW,
                }
            ],
            "total": 1,
            "limit": 50,
            "offset": 0,
        }
    )


class FakeService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.detail = _detail()
        self.snapshot = _snapshot()
        self.failure: Exception | None = None

    def _raise_or_record(self, operation: str, kwargs: dict[str, Any]) -> None:
        if self.failure is not None:
            raise self.failure
        self.calls.append((operation, kwargs))

    def list_cases(self, **kwargs: Any) -> IntegrationCaseListResponse:
        self._raise_or_record("list_cases", kwargs)
        response = _list_response()
        return response.model_copy(update={"limit": kwargs["limit"], "offset": kwargs["offset"]})

    def create_case(self, **kwargs: Any) -> SimpleNamespace:
        self._raise_or_record("create_case", kwargs)
        return SimpleNamespace(
            status_code=201,
            response_json=self.detail.model_dump(mode="json", by_alias=True),
            response_etag='"1"',
        )

    def get_case(self, **kwargs: Any) -> CurrentIntegrationCaseDetail:
        self._raise_or_record("get_case", kwargs)
        return self.detail

    def create_evidence_snapshot(self, **kwargs: Any) -> SimpleNamespace:
        self._raise_or_record("create_evidence_snapshot", kwargs)
        return SimpleNamespace(
            status_code=201,
            response_json=self.snapshot.model_dump(mode="json", by_alias=True),
            response_etag='"1"',
        )

    def list_timeline(self, **kwargs: Any) -> IntegrationCaseTimelineResponse:
        self._raise_or_record("list_timeline", kwargs)
        response = _timeline()
        return response.model_copy(update={"limit": kwargs["limit"], "offset": kwargs["offset"]})


def _app(
    service: FakeService,
    *,
    roles: list[str] | None = None,
    markings: list[str] | None = None,
    principal_override: bool = True,
) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(integration_cases.router)
    if principal_override:
        app.dependency_overrides[require_principal] = lambda: Principal(
            subject="subject:test-001",
            org_id="org-a",
            project_id="project-a",
            roles=roles if roles is not None else ALL_ROLES,
            markings=markings if markings is not None else ["public", "region-cn"],
        )
    app.dependency_overrides[integration_cases.get_integration_case_service] = lambda: service
    return app


def test_five_routes_delegate_verified_context_and_preserve_etags() -> None:
    service = FakeService()
    with TestClient(_app(service), raise_server_exceptions=False) as client:
        listed = client.get("/v1/integration-cases?scope=current")
        created = client.post(
            "/v1/integration-cases",
            json={
                "installationId": INSTALLATION_ID,
                "overlayRevision": "overlay-v1",
                "displayName": "Integration case",
            },
            headers={"Idempotency-Key": "case-create-1"},
        )
        fetched = client.get(f"/v1/integration-cases/{CASE_ID}")
        projected = client.post(
            f"/v1/integration-cases/{CASE_ID}/evidence-snapshots",
            json={},
            headers={"Idempotency-Key": "snapshot-1", "If-Match": '"1"'},
        )
        timeline = client.get(f"/v1/integration-cases/{CASE_ID}/timeline")

    assert [listed.status_code, created.status_code, fetched.status_code, projected.status_code, timeline.status_code] == [200, 201, 200, 201, 200]
    assert created.headers["etag"] == fetched.headers["etag"] == projected.headers["etag"] == '"1"'
    assert listed.json()["scope"] == timeline.json()["scope"] == "current"
    assert [name for name, _kwargs in service.calls] == [
        "list_cases", "create_case", "get_case", "create_evidence_snapshot", "list_timeline"
    ]
    for _name, kwargs in service.calls:
        context = kwargs["context"]
        assert vars(context) == {
            "org_id": "org-a",
            "project_id": "project-a",
            "subject": "subject:test-001",
            "roles": tuple(ALL_ROLES),
            "markings": ("public", "region-cn"),
        }
    assert service.calls[0][1] | {"context": None} == {
        "context": None, "scope": "current", "limit": 50, "offset": 0
    }
    assert service.calls[1][1]["idempotency_key"] == "case-create-1"
    assert service.calls[3][1]["idempotency_key"] == "snapshot-1"
    assert service.calls[3][1]["if_match"] == '"1"'


def test_openapi_freezes_five_operations_security_headers_and_errors() -> None:
    schema = _app(FakeService()).openapi()
    operations = {
        operation["operationId"]: operation
        for path in schema["paths"].values()
        for method, operation in path.items()
        if method in {"get", "post"}
    }
    assert set(operations) == {
        "list_integration_cases",
        "create_integration_case",
        "get_integration_case",
        "create_integration_evidence_snapshot",
        "list_integration_case_timeline",
    }
    assert all(operation["security"] == [{"HTTPBearer": []}] for operation in operations.values())
    create_headers = {item["name"] for item in operations["create_integration_case"]["parameters"]}
    snapshot_headers = {item["name"] for item in operations["create_integration_evidence_snapshot"]["parameters"]}
    assert "Idempotency-Key" in create_headers
    assert "If-Match" not in create_headers
    assert {"Idempotency-Key", "If-Match", "case_id"}.issubset(snapshot_headers)
    assert set(operations["create_integration_evidence_snapshot"]["responses"]) == {
        "201", "400", "401", "403", "404", "409", "422", "428", "500"
    }


@pytest.mark.parametrize(
    ("method", "path", "json_body", "headers"),
    [
        ("post", "/v1/integration-cases", {"installationId": INSTALLATION_ID, "overlayRevision": "overlay-v1", "displayName": "Case", "stage": "production_active"}, {"Idempotency-Key": "create-1"}),
        ("post", f"/v1/integration-cases/{CASE_ID}/evidence-snapshots", {"cutoffAt": "2026-08-04T00:00:00Z"}, {"Idempotency-Key": "snapshot-1", "If-Match": '"1"'}),
    ],
)
def test_strict_body_rejects_projection_injection_before_service(
    method: str, path: str, json_body: dict[str, Any], headers: dict[str, str]
) -> None:
    service = FakeService()
    with TestClient(_app(service), raise_server_exceptions=False) as client:
        response = client.request(method, path, json=json_body, headers=headers)
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"
    assert service.calls == []


@pytest.mark.parametrize(
    "path",
    [
        "/v1/integration-cases",
        "/v1/integration-cases?scope=live",
        "/v1/integration-cases?scope=current&limit=0",
        "/v1/integration-cases?scope=current&unknown=1",
        "/v1/integration-cases?scope=current&scope=current",
        f"/v1/integration-cases/{CASE_ID}?scope=current",
        f"/v1/integration-cases/{CASE_ID}/timeline?unknown=1",
    ],
)
def test_strict_query_rejects_unknown_or_duplicate_fields(path: str) -> None:
    service = FakeService()
    with TestClient(_app(service), raise_server_exceptions=False) as client:
        response = client.get(path)
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"
    assert service.calls == []


def test_command_headers_are_single_strong_and_required_before_service() -> None:
    service = FakeService()
    with TestClient(_app(service), raise_server_exceptions=False) as client:
        missing_key = client.post(
            "/v1/integration-cases",
            json={"installationId": INSTALLATION_ID, "overlayRevision": "overlay-v1", "displayName": "Case"},
        )
        duplicate_key = client.post(
            "/v1/integration-cases",
            json={"installationId": INSTALLATION_ID, "overlayRevision": "overlay-v1", "displayName": "Case"},
            headers=[("Idempotency-Key", "one"), ("Idempotency-Key", "two")],
        )
        missing_if_match = client.post(
            f"/v1/integration-cases/{CASE_ID}/evidence-snapshots",
            json={}, headers={"Idempotency-Key": "snapshot-1"},
        )
        weak_if_match = client.post(
            f"/v1/integration-cases/{CASE_ID}/evidence-snapshots",
            json={}, headers={"Idempotency-Key": "snapshot-2", "If-Match": "W/\"1\""},
        )
        duplicate_if_match = client.post(
            f"/v1/integration-cases/{CASE_ID}/evidence-snapshots",
            json={},
            headers=[
                ("Idempotency-Key", "snapshot-3"),
                ("If-Match", '"1"'),
                ("If-Match", '"2"'),
            ],
        )
    assert [missing_key.json()["code"], duplicate_key.json()["code"]] == ["IDEMPOTENCY_KEY_REQUIRED"] * 2
    assert missing_if_match.status_code == 428
    assert missing_if_match.json()["code"] == "PRECONDITION_REQUIRED"
    assert weak_if_match.status_code == 400
    assert weak_if_match.json()["code"] == "PRECONDITION_INVALID"
    assert duplicate_if_match.status_code == 400
    assert duplicate_if_match.json()["code"] == "PRECONDITION_INVALID"
    assert service.calls == []


def test_dedicated_roles_are_enforced_and_admin_does_not_gain_write_access() -> None:
    service = FakeService()
    with TestClient(_app(service, roles=["admin"]), raise_server_exceptions=False) as client:
        readable = client.get("/v1/integration-cases?scope=current")
        forbidden_create = client.post(
            "/v1/integration-cases",
            json={"installationId": INSTALLATION_ID, "overlayRevision": "overlay-v1", "displayName": "Case"},
            headers={"Idempotency-Key": "create-1"},
        )
        forbidden_snapshot = client.post(
            f"/v1/integration-cases/{CASE_ID}/evidence-snapshots",
            json={}, headers={"Idempotency-Key": "snapshot-1", "If-Match": '"1"'},
        )
    assert readable.status_code == 200
    assert forbidden_create.status_code == forbidden_snapshot.status_code == 403
    assert service.calls == [("list_cases", service.calls[0][1])]


@pytest.mark.parametrize("failure", [MarkingAccessDeniedError(), AssetNotFoundError("other message")])
def test_get_and_timeline_use_one_non_disclosing_not_found(failure: Exception) -> None:
    bodies = []
    for suffix in ("", "/timeline"):
        service = FakeService()
        service.failure = failure
        with TestClient(_app(service), raise_server_exceptions=False) as client:
            response = client.get(f"/v1/integration-cases/{CASE_ID}{suffix}")
        assert response.status_code == 404
        bodies.append(response.json())
    assert bodies[0]["code"] == bodies[1]["code"] == "NOT_FOUND"
    assert bodies[0]["message"] == bodies[1]["message"] == "integration case resource not found"
    assert bodies[0]["details"] is None and bodies[1]["details"] is None


@pytest.mark.parametrize(
    ("failure", "status_code", "code"),
    [
        (IdempotencyConflictError("command conflict"), 409, "IDEMPOTENCY_CONFLICT"),
        (RevisionConflictError("revision conflict"), 409, "REVISION_CONFLICT"),
        (EvidenceReferenceInvalidError("invalid evidence ref"), 422, "EVIDENCE_REFERENCE_INVALID"),
        (EvidenceIntegrityCorruptError(), 500, "EVIDENCE_INTEGRITY_CORRUPT"),
    ],
)
def test_service_errors_keep_frozen_status_and_code(
    failure: Exception, status_code: int, code: str
) -> None:
    service = FakeService()
    service.failure = failure
    with TestClient(_app(service), raise_server_exceptions=False) as client:
        response = client.post(
            f"/v1/integration-cases/{CASE_ID}/evidence-snapshots",
            json={}, headers={"Idempotency-Key": "snapshot-1", "If-Match": '"1"'},
        )
    assert response.status_code == status_code
    assert response.json()["code"] == code


def test_missing_bearer_is_rejected_before_service_factory_result_is_used() -> None:
    service = FakeService()
    with TestClient(_app(service, principal_override=False), raise_server_exceptions=False) as client:
        response = client.get("/v1/integration-cases?scope=current")
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"
    assert service.calls == []


def test_invalid_receipt_etag_fails_closed_without_returning_success() -> None:
    service = FakeService()
    service.snapshot = service.snapshot.model_copy(update={"etag_version": 2})
    with TestClient(_app(service), raise_server_exceptions=False) as client:
        response = client.post(
            f"/v1/integration-cases/{CASE_ID}/evidence-snapshots",
            json={}, headers={"Idempotency-Key": "snapshot-1", "If-Match": '"1"'},
        )
    assert response.status_code == 500
    assert response.json()["code"] == "EVIDENCE_INTEGRITY_CORRUPT"
    assert "etag" not in response.headers
