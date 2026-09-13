from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from aos_api.ecommerce_growth_canonical_router import EcommerceGrowthCanonicalRouter
from aos_api.ecommerce_growth_host_composition import (
    ECOMMERCE_GROWTH_AUTHORITY_KINDS,
    ECOMMERCE_GROWTH_OPERATIONS,
    ECOMMERCE_GROWTH_RECEIPT_KEYS,
    EcommerceGrowthHostAdapterRegistry,
    _REGISTRY_TOKEN,
    build_registration_only_ecommerce_growth_registry,
)
from aos_api.ecommerce_growth_host_ports import EcommerceGrowthHostBlocked, EcommerceGrowthOperationBinding
from aos_api.tenant_scope import TenantScope


RECEIPT = {
    "receiptRef": {
        "resourceType": "BusinessInvestigationCase",
        "resourceId": "case-qyh-001",
        "revision": 3,
        "contentHash": "sha256:" + "a" * 64,
        "receiptId": "receipt-qyh-001",
    }
}


class Result:
    def __init__(self, *, one=None, all_rows=None):
        self._one = one
        self._all = all_rows

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._all


class FakeConnection:
    def __init__(self, dispatch_rows, runtime_rows):
        self.dispatch_rows = dispatch_rows
        self.runtime_rows = runtime_rows
        self.committed = False
        self.issue_queries = 0
        self.lock_queries = 0

    def execute(self, query, params=()):
        compact = " ".join(query.split())
        if "FROM extension_operation_dispatch_binding" in compact and "FOR UPDATE" not in compact:
            self.issue_queries += 1
            operation_id = params[-1]
            row = next((item for item in self.dispatch_rows if item["operation_id"] == operation_id), None)
            return Result(one=deepcopy(row))
        if "FROM public.extension_dispatch_lock_group_a0v_028(%s)" in compact:
            self.lock_queries += 1
            return Result(all_rows=deepcopy(self.dispatch_rows))
        if "FROM extension_runtime_binding" in compact:
            return Result(one=deepcopy(self.runtime_rows.get((params[-2], params[-1]))))
        if compact == "SELECT clock_timestamp() AS checked_at":
            return Result(one={"checked_at": datetime(2026, 9, 8, 8, tzinfo=UTC)})
        raise AssertionError(compact)

    def commit(self):
        self.committed = True


def _fixture(operation_id="ecommerce_growth_case_put"):
    installation, generation, group = uuid4(), uuid4(), uuid4()
    dispatch_rows = [
        {
            "operation_id": operation_id,
            "handler_kind": "extension",
            "installation_id": installation,
            "generation": generation,
            "execution_epoch": 7,
            "operation_fence": False,
            "revision": 5,
            "cutover_group_id": group,
            "cutover_group_revision": 11,
        }
    ]
    runtime_rows = {
        (installation, generation): {
            "installation_id": installation,
            "generation": generation,
            "execution_epoch": 7,
            "revision": 13,
            "desired_state": "enabled",
            "observed_state": "ready",
            "enabled": True,
            "operation_fence": False,
        }
    }
    return dispatch_rows, runtime_rows


def _factory(connection):
    @contextmanager
    def connect(_scope):
        yield connection

    return connect


def _runtime_registry(executor):
    def receipt_for(operation_id):
        if operation_id == "ecommerce_growth_data_fulfill":
            return {
                "requirementRef": RECEIPT["receiptRef"],
            }
        if operation_id == "ecommerce_growth_schedule_trigger":
            return {"occurrenceRef": RECEIPT["receiptRef"]}
        return RECEIPT

    def execute_for(operation_id):
        if operation_id == "ecommerce_growth_case_put":
            return executor

        def execute(**_kwargs):
            return receipt_for(operation_id)

        return execute

    bindings = {
        operation_id: EcommerceGrowthOperationBinding(
            operation_id=operation_id,
            receipt_keys=ECOMMERCE_GROWTH_RECEIPT_KEYS[operation_id],
            authority_kinds=ECOMMERCE_GROWTH_AUTHORITY_KINDS[operation_id],
            revalidate=lambda **_: None,
            execute=execute_for(operation_id),
            verify_receipt=lambda **kwargs: kwargs["receipt"],
        )
        for operation_id in ECOMMERCE_GROWTH_OPERATIONS
    }
    return EcommerceGrowthHostAdapterRegistry._from_host_factory(_REGISTRY_TOKEN, bindings)


def test_canonical_router_issues_readonly_dispatch_then_commits_host_port():
    dispatch_rows, runtime_rows = _fixture()
    connection = FakeConnection(dispatch_rows, runtime_rows)
    seen = {}

    def executor(**kwargs):
        seen["ref"] = kwargs["dispatch_ref"]
        seen["scope"] = kwargs["scope"]
        return RECEIPT

    router = EcommerceGrowthCanonicalRouter(
        _runtime_registry(executor),
        connect_factory=_factory(connection),
    )
    payload = router.dispatch(
        scope=TenantScope("org-org", "dev-project"),
        operation_id="ecommerce_growth_case_put",
        command={"idempotencyKey": "case-1", "businessTitle": "栖月汇经营分析"},
    )
    assert payload == RECEIPT
    assert connection.issue_queries == 1
    assert connection.lock_queries == 1
    assert connection.committed
    ref = seen["ref"]
    row = dispatch_rows[0]
    assert (ref.org_id, ref.project_id) == ("org-org", "dev-project")
    assert ref.operation_id == "ecommerce_growth_case_put"
    assert ref.handler_kind == "extension"
    assert ref.dispatch_revision == 5
    assert ref.execution_epoch == 7
    assert str(ref.installation_id) == str(row["installation_id"])
    assert seen["scope"].key == ("org-org", "dev-project")


def test_canonical_router_rejects_unknown_operation_and_does_not_lock():
    dispatch_rows, runtime_rows = _fixture()
    connection = FakeConnection(dispatch_rows, runtime_rows)
    router = EcommerceGrowthCanonicalRouter(
        _runtime_registry(lambda **_: RECEIPT),
        connect_factory=_factory(connection),
    )
    with pytest.raises(EcommerceGrowthHostBlocked, match="unknown operation"):
        router.dispatch(
            scope=TenantScope("org-org", "dev-project"),
            operation_id="ecommerce_growth_secret_export",
            command={"businessTitle": "栖月汇"},
        )
    assert connection.issue_queries == 0
    assert connection.lock_queries == 0
    assert not connection.committed


def test_canonical_router_registration_only_still_requires_runtime_wiring():
    dispatch_rows, runtime_rows = _fixture()
    connection = FakeConnection(dispatch_rows, runtime_rows)
    router = EcommerceGrowthCanonicalRouter(
        build_registration_only_ecommerce_growth_registry(),
        connect_factory=_factory(connection),
    )
    with pytest.raises(EcommerceGrowthHostBlocked, match="AR2_7D_RUNTIME_WIRING_REQUIRED"):
        router.dispatch(
            scope=TenantScope("org-org", "dev-project"),
            operation_id="ecommerce_growth_case_put",
            command={"businessTitle": "栖月汇经营分析"},
        )
    assert connection.issue_queries == 1
    assert not connection.committed


def test_canonical_router_rejects_fenced_binding_during_issue():
    dispatch_rows, runtime_rows = _fixture()
    dispatch_rows[0]["operation_fence"] = True
    connection = FakeConnection(dispatch_rows, runtime_rows)
    router = EcommerceGrowthCanonicalRouter(
        _runtime_registry(lambda **_: RECEIPT),
        connect_factory=_factory(connection),
    )
    with pytest.raises(EcommerceGrowthHostBlocked, match="not executable"):
        router.dispatch(
            scope=TenantScope("org-org", "dev-project"),
            operation_id="ecommerce_growth_case_put",
            command={"businessTitle": "栖月汇"},
        )
    assert connection.lock_queries == 0
    assert not connection.committed


def test_canonical_router_legacy_without_compat_service_is_blocked():
    dispatch_rows, runtime_rows = _fixture()
    dispatch_rows[0].update(
        handler_kind="legacy",
        installation_id=None,
        generation=None,
        execution_epoch=None,
    )
    connection = FakeConnection(dispatch_rows, runtime_rows)
    router = EcommerceGrowthCanonicalRouter(
        _runtime_registry(lambda **_: RECEIPT),
        connect_factory=_factory(connection),
    )
    with pytest.raises(EcommerceGrowthHostBlocked, match="legacy"):
        router.dispatch(
            scope=TenantScope("org-org", "dev-project"),
            operation_id="ecommerce_growth_case_put",
            command={"businessTitle": "栖月汇"},
        )
    assert connection.lock_queries == 0
    assert not connection.committed
