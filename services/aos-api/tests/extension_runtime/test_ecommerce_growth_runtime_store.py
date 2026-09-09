from datetime import UTC, datetime
from uuid import uuid4

import pytest

from aos_api.ecommerce_growth_host_ports import EcommerceGrowthDispatchSnapshot, HostTransaction
from aos_api.ecommerce_growth_runtime_store import (
    BoundEcommerceGrowthRuntimeStore,
    EcommerceGrowthRuntimeReceiptConflict,
)
from aos_api.tenant_scope import TenantScope


HASH = "sha256:" + "a" * 64
TARGET = {
    "resourceType": "BusinessInvestigationCaseRevision",
    "resourceId": "case-qyh-001",
    "revision": 1,
    "contentHash": HASH,
    "receiptId": "receipt-qyh-001",
}


class Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def execute(self, query, params=()):
        self.calls.append((query, params))
        return Result(self.row)


def snapshot(operation="ecommerce_growth_case_put"):
    return EcommerceGrowthDispatchSnapshot(
        operation_id=operation,
        dispatch_revision=4,
        installation_id=uuid4(),
        generation=uuid4(),
        execution_epoch=7,
        cutover_group_id=uuid4(),
        cutover_group_revision=9,
        runtime_revision=11,
        checked_at=datetime(2026, 9, 8, 8, tzinfo=UTC),
    )


def test_store_persists_and_returns_exact_response():
    response = {"receiptRef": TARGET, "businessTitle": "栖月汇经营分析"}
    connection = Connection({"response": response, "replayed": False})
    store = BoundEcommerceGrowthRuntimeStore(
        HostTransaction(connection), TenantScope("org-org", "dev-project")
    )
    result = store.put(
        operation_id="ecommerce_growth_case_put",
        idempotency_key="case-qyh-001",
        request_hash=HASH,
        dispatch=snapshot(),
        response=response,
        target_receipt_ref=TARGET,
        actor="test-author",
        occurred_at=datetime(2026, 9, 8, 8, tzinfo=UTC),
    )
    assert result.response == response and result.replayed is False
    assert "ecommerce_growth_runtime_receipt_put_ar2_005" in connection.calls[0][0]
    assert connection.calls[0][1][0:3] == (
        "ecommerce_growth_case_put",
        "case-qyh-001",
        HASH,
    )


@pytest.mark.parametrize(
    "change",
    [
        {"operation_id": "unknown"},
        {"idempotency_key": ""},
        {"request_hash": "bad"},
        {"actor": ""},
        {"occurred_at": datetime(2026, 9, 8, 8)},
    ],
)
def test_store_rejects_invalid_invocation_identity(change):
    args = dict(
        operation_id="ecommerce_growth_case_put",
        idempotency_key="case-qyh-001",
        request_hash=HASH,
        dispatch=snapshot(),
        response={"receiptRef": TARGET},
        target_receipt_ref=TARGET,
        actor="test-author",
        occurred_at=datetime(2026, 9, 8, 8, tzinfo=UTC),
    )
    args.update(change)
    store = BoundEcommerceGrowthRuntimeStore(
        HostTransaction(Connection(None)), TenantScope("org-org", "dev-project")
    )
    with pytest.raises(ValueError):
        store.put(**args)


def test_store_rejects_response_without_target_or_persistence_drift():
    store = BoundEcommerceGrowthRuntimeStore(
        HostTransaction(Connection(None)), TenantScope("org-org", "dev-project")
    )
    base = dict(
        operation_id="ecommerce_growth_case_put",
        idempotency_key="case-qyh-001",
        request_hash=HASH,
        dispatch=snapshot(),
        target_receipt_ref=TARGET,
        actor="test-author",
        occurred_at=datetime(2026, 9, 8, 8, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="contain"):
        store.put(response={"receiptRef": {**TARGET, "revision": 2}}, **base)
    with pytest.raises(ValueError, match="contain"):
        store.put(response={"receiptRef": {**TARGET, "revision": True}}, **base)
    drift = BoundEcommerceGrowthRuntimeStore(
        HostTransaction(Connection({"response": {"receiptRef": {**TARGET, "revision": 2}}, "replayed": True})),
        TenantScope("org-org", "dev-project"),
    )
    with pytest.raises(EcommerceGrowthRuntimeReceiptConflict, match="drifted"):
        drift.put(response={"receiptRef": TARGET}, **base)


def test_read_is_tenant_scoped_and_returns_copy():
    response = {"receiptRef": TARGET}
    connection = Connection({"response": response})
    store = BoundEcommerceGrowthRuntimeStore(
        HostTransaction(connection), TenantScope("org-org", "dev-project")
    )
    observed = store.read(operation_id="ecommerce_growth_case_put", idempotency_key="case-qyh-001")
    assert observed == response and observed is not response
    assert connection.calls[0][1] == (
        "org-org",
        "dev-project",
        "ecommerce_growth_case_put",
        "case-qyh-001",
    )
    assert "public.ecommerce_growth_runtime_command_receipt" in connection.calls[0][0]


def test_read_exact_uses_tenant_operation_and_complete_receipt_ref():
    response = {"receiptRef": TARGET, "requestHash": HASH}
    connection = Connection(
        [
            {
                "idempotency_key": "analysis-start-1",
                "request_hash": HASH,
                "response": response,
                "target_receipt_ref": TARGET,
            }
        ]
    )
    connection.execute = lambda query, params=(): (
        connection.calls.append((query, params))
        or type("Rows", (), {"fetchall": lambda self: connection.row})()
    )
    store = BoundEcommerceGrowthRuntimeStore(
        HostTransaction(connection), TenantScope("org-org", "dev-project")
    )
    observed = store.read_exact(
        operation_id="ecommerce_growth_analysis_advance", receipt_ref=TARGET
    )
    assert observed == response and observed is not response
    assert connection.calls[0][1][0:3] == (
        "org-org",
        "dev-project",
        "ecommerce_growth_analysis_advance",
    )
    import json

    assert json.loads(connection.calls[0][1][3]) == TARGET
    assert "public.ecommerce_growth_runtime_command_receipt" in connection.calls[0][0]


def test_read_exact_rejects_duplicate_or_persisted_drift():
    base = {
        "idempotency_key": "analysis-start-1",
        "request_hash": HASH,
        "response": {"receiptRef": TARGET, "requestHash": HASH},
        "target_receipt_ref": TARGET,
    }

    def store_for(rows):
        connection = Connection(rows)
        connection.execute = lambda query, params=(): type(
            "Rows", (), {"fetchall": lambda self: connection.row}
        )()
        return BoundEcommerceGrowthRuntimeStore(
            HostTransaction(connection), TenantScope("org-org", "dev-project")
        )

    with pytest.raises(EcommerceGrowthRuntimeReceiptConflict, match="unique"):
        store_for([base, {**base, "idempotency_key": "analysis-start-2"}]).read_exact(
            operation_id="ecommerce_growth_analysis_advance", receipt_ref=TARGET
        )
    with pytest.raises(EcommerceGrowthRuntimeReceiptConflict, match="request hash"):
        store_for([{**base, "response": {"receiptRef": TARGET, "requestHash": "sha256:" + "b" * 64}}]).read_exact(
            operation_id="ecommerce_growth_analysis_advance", receipt_ref=TARGET
        )
    with pytest.raises(ValueError, match="exact reference"):
        store_for([]).read_exact(
            operation_id="ecommerce_growth_analysis_advance",
            receipt_ref={**TARGET, "revision": True},
        )
