"""W2-01A strict Operations view contract tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_operations_contracts import (
    OPERATIONS_SCHEMA_VERSION,
    OperationsSliceId,
    WorkshopOperationsViewEnvelope,
)
from aos_api.ecommerce_operation_case_contracts import OperationCaseRevision
from aos_api.ecommerce_workshop_operations import EcommerceWorkshopOperations


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
