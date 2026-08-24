"""W2-01A GET-only Operations view API shell tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.auth import Principal, require_principal
from aos_api.asset_registry.errors import AssetNotFoundError
from aos_api.errors import register_exception_handlers
from aos_api.routers import ecommerce_workshop
from aos_api.ecommerce_workshop_operations import EcommerceWorkshopOperations
from aos_api.ecommerce_operation_commands import EcommerceOperationCommands
from aos_api.ecommerce_operation_command_execution_contracts import (
    OperationCommandExecutionEnvelope,
)


class FakeCatalog:
    def __init__(self, *, installed: bool = True) -> None:
        self.installed = installed
        self.calls: list[dict[str, object]] = []

    def get_readiness(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if not self.installed:
            raise AssetNotFoundError("not installed")
        return object()


def _client(
    catalog: FakeCatalog | None = None,
    operations: EcommerceWorkshopOperations | None = None,
    commands: EcommerceOperationCommands | None = None,
    command_service: object | None = None,
) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(ecommerce_workshop.router)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="user:test",
        org_id="org-org",
        project_id="dev-project",
        roles=["operator"],
        markings=["public"],
    )
    app.dependency_overrides[ecommerce_workshop.get_ecommerce_workshop_catalog] = (
        lambda: catalog or FakeCatalog()
    )
    if operations is not None:
        app.dependency_overrides[
            ecommerce_workshop.get_ecommerce_workshop_operations
        ] = lambda: operations
    if commands is not None:
        app.dependency_overrides[
            ecommerce_workshop.get_ecommerce_operation_commands
        ] = lambda: commands
    if command_service is not None:
        app.dependency_overrides[
            ecommerce_workshop.get_ecommerce_operation_command_service
        ] = lambda: command_service
    return TestClient(app, raise_server_exceptions=False)


def test_operations_shell_is_tenant_bound_and_structurally_blocked() -> None:
    class ObjectReader:
        def read(self, **kwargs):
            return []

    class InventoryReader:
        def read(self, **kwargs):
            return type("Inventory", (), {"items": []})()

    class CaseStore:
        def list_cases(self, scope, *, limit=50):
            return []

    class AftersaleReader:
        def read(self, **kwargs):
            return []

    operations = EcommerceWorkshopOperations(
        object_reader=ObjectReader(),  # type: ignore[arg-type]
        inventory_reader=InventoryReader(),  # type: ignore[arg-type]
        aftersale_reader=AftersaleReader(),  # type: ignore[arg-type]
        case_store=CaseStore(),  # type: ignore[arg-type]
    )
    catalog = FakeCatalog()
    with _client(catalog, operations) as client:
        response = client.get("/v1/ecommerce-workshop/views/operations")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert body["readiness"] == "degraded"
    assert [item["sliceId"] for item in body["slices"]] == [
        "orders",
        "orderLines",
        "inventory",
        "shipments",
        "payments",
        "aftersaleEvents",
        "operationCases",
    ]
    assert [item["status"] for item in body["slices"]] == [
        "ready",
        "ready",
        "ready",
        "ready",
        "ready",
        "ready",
        "ready",
    ]
    inventory = body["slices"][2]
    aftersales = body["slices"][5]
    assert inventory["authorityRefs"][0]["resourceType"] == "ProductSku"
    assert aftersales["authorityRefs"][0]["resourceType"] == "AfterSalesEvent"
    assert inventory["blockers"] == []
    assert inventory["authorityRefs"][0]["receiptId"].startswith("d0-")
    assert aftersales["blockers"] == []
    assert aftersales["authorityRefs"][0]["receiptId"] == (
        "d0-aftersale-canonical-reader-code-20260824"
    )
    assert catalog.calls == [
        {
            "module_id": "ecommerce.operations",
            "org_id": "org-org",
            "project_id": "dev-project",
            "roles": ["operator"],
            "markings": ["public"],
        }
    ]


def test_operations_api_rejects_scope_injection_and_non_get_methods() -> None:
    with _client() as client:
        injected = client.get(
            "/v1/ecommerce-workshop/views/operations?orgId=dev-org"
        )
        posted = client.post("/v1/ecommerce-workshop/views/operations")

    assert injected.status_code == 400
    assert injected.json()["code"] == "VALIDATION"
    assert posted.status_code == 405


def test_operations_api_fails_closed_when_module_is_not_installed() -> None:
    with _client(FakeCatalog(installed=False)) as client:
        response = client.get("/v1/ecommerce-workshop/views/operations")

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_openapi_exposes_only_the_operations_get_surface() -> None:
    with _client() as client:
        document = client.get("/openapi.json").json()

    surface = document["paths"]["/v1/ecommerce-workshop/views/operations"]
    assert set(surface) == {"get"}
    assert surface["get"]["operationId"] == "ecommerceWorkshopOperationsViewGet"


def test_operation_command_readiness_is_get_only_and_scope_safe() -> None:
    catalog = FakeCatalog()
    with _client(catalog, commands=EcommerceOperationCommands()) as client:
        response = client.get(
            "/v1/ecommerce-workshop/commands/operations/readiness"
        )
        injected = client.get(
            "/v1/ecommerce-workshop/commands/operations/readiness?orgId=dev-org"
        )
        posted = client.post(
            "/v1/ecommerce-workshop/commands/operations/readiness"
        )

    assert response.status_code == 200
    assert response.json()["tenant"] == {
        "orgId": "org-org",
        "projectId": "dev-project",
    }
    assert len(response.json()["commands"]) == 6
    assert injected.status_code == 400
    assert posted.status_code == 405
    assert catalog.calls[0]["org_id"] == "org-org"


def test_openapi_exposes_only_operation_command_readiness_get() -> None:
    with _client() as client:
        document = client.get("/openapi.json").json()

    surface = document["paths"][
        "/v1/ecommerce-workshop/commands/operations/readiness"
    ]
    assert set(surface) == {"get"}
    assert surface["get"]["operationId"] == (
        "ecommerceWorkshopOperationCommandReadinessGet"
    )


class FakeOperationCommandService:
    def __init__(self) -> None:
        self.calls = []

    def classify(self, principal, idempotency_key, body):
        self.calls.append((principal, idempotency_key, body))
        return self._response(principal, idempotency_key, body, "classify")

    def change_membership(self, principal, idempotency_key, body):
        self.calls.append((principal, idempotency_key, body))
        return self._response(principal, idempotency_key, body, "changeMembership")

    def manage_sla(self, principal, idempotency_key, body):
        self.calls.append((principal, idempotency_key, body))
        return self._response(principal, idempotency_key, body, "manageSla")

    @staticmethod
    def _response(principal, idempotency_key, body, command_id):
        return OperationCommandExecutionEnvelope.model_validate(
            {
                "tenant": {"orgId": principal.org_id, "projectId": principal.project_id},
                "commandId": command_id,
                "status": "applied",
                "proposalId": body.governance.proposal_id,
                "leaseId": body.governance.lease_id,
                "operationReceipt": {
                    "tenant": {"orgId": principal.org_id, "projectId": principal.project_id},
                    "receiptId": "op-receipt-1",
                    "operation": "operation_classification.append",
                    "idempotencyKey": idempotency_key,
                    "requestHash": "a" * 64,
                    "resultRef": {"resourceId": "classification-1", "revision": 1, "contentHash": "a" * 64},
                    "createdBy": principal.subject,
                    "createdAt": datetime(2026, 8, 24, tzinfo=UTC),
                },
            }
        )


def _classification_payload() -> dict:
    return {
        "governance": {
            "proposalId": "proposal-1",
            "proposalVersion": 2,
            "proposalHash": "b" * 64,
            "approvalEventIds": ["approval-1"],
            "leaseId": "lease-1",
        },
        "expectedVersion": 0,
        "revision": {
            "tenant": {"orgId": "org-org", "projectId": "dev-project"},
            "decisionId": "classification-1",
            "revision": 1,
            "originalRef": {
                "tenant": {"orgId": "org-org", "projectId": "dev-project"},
                "resourceType": "Order",
                "resourceId": "order-1",
                "contentHash": "a" * 64,
                "sourceUpdatedAt": "2026-08-24T00:00:00Z",
            },
            "classifierRef": {"resourceId": "classifier-1", "revision": 1, "contentHash": "a" * 64},
            "aggregationPolicyRef": {"resourceId": "policy-1", "revision": 1, "contentHash": "a" * 64},
            "classification": "fulfillment-risk",
            "confidence": 0.9,
            "reason": "exact source evidence",
            "contentHash": "a" * 64,
            "actor": "user:test",
            "createdAt": "2026-08-24T00:00:00Z",
        },
    }


def _membership_payload() -> dict:
    return {
        "governance": _classification_payload()["governance"],
        "expectedVersion": 0,
        "revision": {
            "tenant": {"orgId": "org-org", "projectId": "dev-project"},
            "decisionId": "membership-1",
            "revision": 1,
            "decisionType": "attach",
            "predecessorCaseRefs": [],
            "successorCaseRefs": [],
            "movedOriginals": [
                {
                    "tenant": {"orgId": "org-org", "projectId": "dev-project"},
                    "resourceType": "Order",
                    "resourceId": "order-1",
                    "contentHash": "a" * 64,
                    "sourceUpdatedAt": "2026-08-24T00:00:00Z",
                }
            ],
            "beforeTotal": 1,
            "afterTotal": 1,
            "unmatchedCount": 0,
            "conflictedCount": 0,
            "reason": "attach exact original",
            "contentHash": "a" * 64,
            "actor": "user:test",
            "createdAt": "2026-08-24T00:00:00Z",
        },
    }


def _sla_payload() -> dict:
    return {
        "governance": _classification_payload()["governance"],
        "expectedVersion": 0,
        "revision": {
            "tenant": {"orgId": "org-org", "projectId": "dev-project"},
            "decisionId": "sla-clock-1",
            "revision": 1,
            "caseRef": {"resourceId": "case-1", "revision": 1, "contentHash": "a" * 64},
            "policyRef": {"resourceId": "sla-policy-1", "revision": 1, "contentHash": "a" * 64},
            "operation": "start",
            "sourceEventTime": "2026-08-24T00:00:00Z",
            "reason": "start exact SLA clock",
            "contentHash": "a" * 64,
            "actor": "user:test",
            "createdAt": "2026-08-24T00:00:00Z",
        },
    }


def test_classify_command_requires_idempotency_and_rejects_body_scope_injection() -> None:
    service = FakeOperationCommandService()
    payload = _classification_payload()
    with _client(command_service=service) as client:
        missing_key = client.post(
            "/v1/ecommerce-workshop/commands/operations/classify", json=payload
        )
        injected = client.post(
            "/v1/ecommerce-workshop/commands/operations/classify",
            headers={"Idempotency-Key": "command-key-1"},
            json={**payload, "orgId": "dev-org"},
        )
        response = client.post(
            "/v1/ecommerce-workshop/commands/operations/classify",
            headers={"Idempotency-Key": "command-key-1"},
            json=payload,
        )

    assert missing_key.status_code == 400
    assert injected.status_code == 400
    assert response.status_code == 200
    assert response.json()["operationReceipt"]["receiptId"] == "op-receipt-1"
    assert service.calls[0][0].org_id == "org-org"
    assert service.calls[0][1] == "command-key-1"


@pytest.mark.parametrize(
    ("path", "payload_factory", "command_id"),
    [
        ("change-membership", _membership_payload, "changeMembership"),
        ("manage-sla", _sla_payload, "manageSla"),
    ],
)
def test_membership_and_sla_commands_are_explicit_strict_posts(
    path, payload_factory, command_id
) -> None:
    service = FakeOperationCommandService()
    payload = payload_factory()
    with _client(command_service=service) as client:
        missing_key = client.post(
            f"/v1/ecommerce-workshop/commands/operations/{path}", json=payload
        )
        injected = client.post(
            f"/v1/ecommerce-workshop/commands/operations/{path}",
            headers={"Idempotency-Key": "command-key-b2b"},
            json={**payload, "actorId": "user:other"},
        )
        response = client.post(
            f"/v1/ecommerce-workshop/commands/operations/{path}",
            headers={"Idempotency-Key": "command-key-b2b"},
            json=payload,
        )

    assert missing_key.status_code == 400
    assert injected.status_code == 400
    assert response.status_code == 200
    assert response.json()["commandId"] == command_id
    assert service.calls[0][0].org_id == "org-org"


def test_openapi_exposes_four_explicit_internal_command_posts() -> None:
    with _client() as client:
        document = client.get("/openapi.json").json()

    classify = document["paths"]["/v1/ecommerce-workshop/commands/operations/classify"]
    create_case = document["paths"]["/v1/ecommerce-workshop/commands/operations/create-case"]
    membership = document["paths"]["/v1/ecommerce-workshop/commands/operations/change-membership"]
    sla = document["paths"]["/v1/ecommerce-workshop/commands/operations/manage-sla"]
    assert set(classify) == {"post"}
    assert set(create_case) == {"post"}
    assert classify["post"]["operationId"] == "ecommerceWorkshopOperationClassifyPost"
    assert create_case["post"]["operationId"] == "ecommerceWorkshopOperationCreateCasePost"
    assert membership["post"]["operationId"] == "ecommerceWorkshopOperationChangeMembershipPost"
    assert sla["post"]["operationId"] == "ecommerceWorkshopOperationManageSlaPost"
