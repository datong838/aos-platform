"""W2-01A strict Operations view contract tests."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_operations_contracts import (
    OPERATIONS_SCHEMA_VERSION,
    OperationsSliceId,
    WorkshopOperationsViewEnvelope,
)
from aos_api.ecommerce_operation_case_contracts import OperationCaseRevision
from aos_api.ecommerce_workshop_operations import EcommerceWorkshopOperations
from aos_api.ecommerce_operations_object_reader import (
    OperationsObjectReadError,
    OperationsObjectRef,
)


NOW = datetime(2026, 8, 24, 4, 30, tzinfo=UTC)


def _blocked_slice(slice_id: str) -> dict[str, object]:
    return {
        "sliceId": slice_id,
        "status": "blocked",
        "dataCutoff": NOW,
        "authorityRefs": [],
        "blockers": [
            {
                "code": f"{slice_id.upper()}_AUTHORITY_NOT_READY",
                "dependency": f"ecommerce.{slice_id}",
                "requiredAction": "provide exact authority receipt",
            }
        ],
        "countLedger": {
            "sourceTotal": 0,
            "attached": 0,
            "unmatched": 0,
            "conflicted": 0,
        },
    }


def _envelope() -> dict[str, object]:
    return {
        "schemaVersion": OPERATIONS_SCHEMA_VERSION,
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "evaluatedAt": NOW,
        "dataCutoff": NOW,
        "readiness": "degraded",
        "slices": [_blocked_slice(item.value) for item in OperationsSliceId],
        "page": {"limit": 50, "count": 0, "hasMore": False, "nextCursor": None},
    }


def test_envelope_requires_all_seven_canonical_slices() -> None:
    envelope = WorkshopOperationsViewEnvelope.model_validate(_envelope())
    assert [item.slice_id for item in envelope.slices] == list(OperationsSliceId)
    assert envelope.page.count == 0

    missing = _envelope()
    missing["slices"] = missing["slices"][:-1]  # type: ignore[index]
    with pytest.raises(ValidationError):
        WorkshopOperationsViewEnvelope.model_validate(missing)


def test_contract_fails_closed_on_naive_time_count_drift_and_false_ready() -> None:
    naive = _envelope()
    naive["evaluatedAt"] = datetime(2026, 8, 24, 4, 30)
    with pytest.raises(ValidationError):
        WorkshopOperationsViewEnvelope.model_validate(naive)

    drift = _envelope()
    drift["slices"][0]["countLedger"]["sourceTotal"] = 1  # type: ignore[index]
    with pytest.raises(ValidationError):
        WorkshopOperationsViewEnvelope.model_validate(drift)

    false_ready = _envelope()
    false_ready["slices"][0]["status"] = "ready"  # type: ignore[index]
    with pytest.raises(ValidationError):
        WorkshopOperationsViewEnvelope.model_validate(false_ready)


def test_exact_authority_ref_requires_sha256_and_positive_revision() -> None:
    ready = _envelope()
    first = ready["slices"][0]  # type: ignore[index]
    first["status"] = "ready"
    first["blockers"] = []
    first["authorityRefs"] = [
        {
            "resourceType": "Order",
            "resourceId": "order-read-model",
            "revision": 0,
            "contentHash": "not-a-hash",
            "receiptId": "receipt-order-v1",
        }
    ]
    with pytest.raises(ValidationError):
        WorkshopOperationsViewEnvelope.model_validate(ready)


def test_operation_case_slice_consumes_exact_w3_12a_authority() -> None:
    case = OperationCaseRevision.model_validate(
        {
            "tenant": {"orgId": "org-org", "projectId": "dev-project"},
            "caseId": "case-1",
            "revision": 1,
            "version": 1,
            "status": "open",
            "aggregationPolicyRef": {
                "resourceId": "policy-1",
                "revision": 1,
                "contentHash": "a" * 64,
            },
            "memberRefs": [],
            "contentHash": "b" * 64,
            "actor": "user:operator",
            "createdAt": NOW,
        }
    )

    class CaseStore:
        def list_cases(self, scope, *, limit=50):
            assert scope.key == ("org-org", "dev-project")
            assert limit == 50
            return [case]

    envelope = EcommerceWorkshopOperations(
        clock=lambda: NOW,
        case_store=CaseStore(),  # type: ignore[arg-type]
    ).read(org_id="org-org", project_id="dev-project")
    operation_cases = envelope.slices[-1]
    assert operation_cases.status.value == "ready"
    assert operation_cases.count_ledger.attached == 1
    assert operation_cases.authority_refs[1].resource_id == "case-1"
    assert envelope.page.count == 1


def test_transaction_and_inventory_slices_are_ready_from_bounded_readers() -> None:
    class ObjectReader:
        def __init__(self) -> None:
            self.calls: list[tuple[str, datetime, int]] = []

        def read(self, *, object_type, cutoff, limit, **scope):
            assert scope == {"org_id": "org-org", "project_id": "dev-project"}
            self.calls.append((object_type, cutoff, limit))
            return [
                OperationsObjectRef(
                    objectType=object_type,
                    objectId=f"{object_type.lower()}-1",
                    contentHash="sha256:" + "a" * 64,
                    sourceUpdatedAt=NOW,
                )
            ]

    class InventoryReader:
        def read(self, *, cutoff, limit, **scope):
            assert cutoff == NOW
            assert limit == 50
            assert scope == {"org_id": "org-org", "project_id": "dev-project"}
            return SimpleNamespace(items=[object()])

    class EmptyCaseStore:
        def list_cases(self, scope, *, limit=50):
            return []

    object_reader = ObjectReader()
    envelope = EcommerceWorkshopOperations(
        clock=lambda: NOW,
        object_reader=object_reader,  # type: ignore[arg-type]
        inventory_reader=InventoryReader(),  # type: ignore[arg-type]
        case_store=EmptyCaseStore(),  # type: ignore[arg-type]
    ).read(org_id="org-org", project_id="dev-project")

    assert [item.status.value for item in envelope.slices[:5]] == ["ready"] * 5
    assert [item.count_ledger.attached for item in envelope.slices[:5]] == [1] * 5
    assert envelope.slices[5].status.value == "blocked"
    assert envelope.slices[6].status.value == "ready"
    assert envelope.page.count == 5
    assert [call[0] for call in object_reader.calls] == [
        "Order",
        "OrderLine",
        "Shipment",
        "Payment",
    ]


def test_one_transaction_reader_failure_blocks_only_its_slice() -> None:
    class ObjectReader:
        def read(self, *, object_type, **kwargs):
            if object_type == "Payment":
                raise OperationsObjectReadError("failed closed")
            return []

    class InventoryReader:
        def read(self, **kwargs):
            return SimpleNamespace(items=[])

    class EmptyCaseStore:
        def list_cases(self, scope, *, limit=50):
            return []

    envelope = EcommerceWorkshopOperations(
        clock=lambda: NOW,
        object_reader=ObjectReader(),  # type: ignore[arg-type]
        inventory_reader=InventoryReader(),  # type: ignore[arg-type]
        case_store=EmptyCaseStore(),  # type: ignore[arg-type]
    ).read(org_id="org-org", project_id="dev-project")

    assert envelope.slices[4].status.value == "blocked"
    assert envelope.slices[4].blockers[0].code == "PAYMENTS_READ_FAILED_CLOSED"
    assert all(item.status.value == "ready" for item in envelope.slices[:4])
