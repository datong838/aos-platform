from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_aftersale_event_reader import AftersaleEventOriginal
from aos_api.ecommerce_inventory_reader import EcommerceInventoryReaderError
from aos_api.ecommerce_operation_case_contracts import OperationCaseRevision
from aos_api.ecommerce_operation_case_workspace import EcommerceOperationCaseWorkspace
from aos_api.ecommerce_operations_object_reader import OperationsObjectRef


NOW = datetime(2026, 9, 4, 13, 0, tzinfo=UTC)
TENANT = {"orgId": "org-org", "projectId": "dev-project"}


def _object(object_type: str, object_id: str, digest: str) -> OperationsObjectRef:
    return OperationsObjectRef.model_validate({
        "objectType": object_type, "objectId": object_id,
        "contentHash": f"sha256:{digest}", "sourceUpdatedAt": NOW,
    })


class ObjectReader:
    def read(self, *, object_type, **kwargs):
        digest = {"Order": "a", "Shipment": "b", "Payment": "c"}[object_type]
        return [_object(object_type, f"{object_type.lower()}-1", digest * 64)]


class InventoryReader:
    def read(self, **kwargs):
        return SimpleNamespace(items=[
            SimpleNamespace(object_id="sku-complete", stock=8, stock_alarm=2, stock_health="healthy", source_updated_at=NOW, revision=SimpleNamespace(content_hash="sha256:" + "d" * 64)),
            SimpleNamespace(object_id="sku-missing", stock=None, stock_alarm=2, stock_health=None, source_updated_at=NOW, revision=SimpleNamespace(content_hash="sha256:" + "e" * 64)),
        ])


class AftersaleReader:
    def read(self, **kwargs):
        return [AftersaleEventOriginal.model_validate({
            "eventId": "after-1", "sourceRevision": 1, "sourceHash": "f" * 64,
            "eventType": "refund_requested", "status": "open", "occurredAt": NOW,
            "orderRef": {"resourceId": "order-1", "revision": 1, "contentHash": "7" * 64},
        })]


def _case(member_hash: str = "a" * 64) -> OperationCaseRevision:
    return OperationCaseRevision.model_validate({
        "tenant": TENANT, "caseId": "case-1", "revision": 1, "version": 1,
        "status": "open", "priority": "normal",
        "aggregationPolicyRef": {"resourceId": "policy-1", "revision": 1, "contentHash": "8" * 64},
        "memberRefs": [{"tenant": TENANT, "resourceType": "Order", "resourceId": "order-1", "contentHash": member_hash, "sourceUpdatedAt": NOW}],
        "contentHash": "c" * 64, "actor": "user:operator", "createdAt": NOW,
    })


class CaseStore:
    def __init__(self, case=None): self.case = case or _case()
    def list_cases(self, scope, *, limit=50): return [self.case]


def _service(*, inventory_reader=None, case_store=None):
    return EcommerceOperationCaseWorkspace(
        clock=lambda: NOW, object_reader=ObjectReader(),
        inventory_reader=inventory_reader or InventoryReader(),
        aftersale_reader=AftersaleReader(), case_store=case_store or CaseStore(),
    )


def test_composes_exact_assignment_candidates_and_conserved_ledger() -> None:
    body = _service().read(org_id="org-org", project_id="dev-project")
    assert body.status == "ready"
    assert body.ledger.source_total == 6
    assert body.ledger.assigned == 1
    assert body.ledger.unassigned == 5
    assert body.ledger.candidates == 2
    assert body.ledger.open_cases == 1
    assert {item.kind for item in body.candidates} == {"inventory_data_gap", "aftersale_followup"}
    assert body.external_effect_allowed is False


def test_exact_hash_drift_keeps_same_id_fact_unassigned() -> None:
    body = _service(case_store=CaseStore(_case("9" * 64))).read(org_id="org-org", project_id="dev-project")
    assert body.ledger.assigned == 0
    assert any(item.resource_id == "order-1" for item in body.available_refs)


def test_one_source_failure_keeps_other_sources_as_partial() -> None:
    class FailedInventory:
        def read(self, **kwargs): raise EcommerceInventoryReaderError("failed")
    body = _service(inventory_reader=FailedInventory()).read(org_id="org-org", project_id="dev-project")
    assert body.status == "partial"
    assert next(item for item in body.sources if item.source_id == "inventory").status == "blocked"
    assert next(item for item in body.sources if item.source_id == "orders").count == 1
    assert body.ledger.source_total == 4


def test_case_tenant_drift_blocks_case_source_without_hiding_business_facts() -> None:
    drifted = _case().model_copy(
        update={"tenant": TenantContext(org_id="dev-org", project_id="dev-project")}
    )
    body = _service(case_store=CaseStore(drifted)).read(
        org_id="org-org", project_id="dev-project"
    )

    case_source = next(
        item for item in body.sources if item.source_id == "operationCases"
    )
    assert body.status == "partial"
    assert case_source.status == "blocked"
    assert body.cases == []
    assert body.ledger.source_total == 6
    assert body.ledger.assigned == 0


def test_naive_cutoff_is_rejected_before_any_source_read() -> None:
    service = _service()
    service._clock = lambda: datetime(2026, 9, 4, 13, 0)  # type: ignore[assignment]

    with pytest.raises(ValueError, match="timezone"):
        service.read(org_id="org-org", project_id="dev-project")
