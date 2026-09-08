from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

from aos_api.ecommerce_growth_host_composition import (
    ECOMMERCE_GROWTH_OPERATIONS,
    EcommerceGrowthHostAdapterRegistry,
    build_ecommerce_growth_host_ports,
    build_registration_only_ecommerce_growth_registry,
)
from aos_api.ecommerce_growth_host_ports import (
    EcommerceGrowthHostBlocked,
    EcommerceGrowthHostConflict,
    EcommerceGrowthHostError,
    EcommerceGrowthOperationBinding,
    LockedEcommerceGrowthHostPort,
)


ROOT = Path(__file__).resolve().parents[4]
for dependency in (
    ROOT / "packages/aos-extension-sdk/python",
    ROOT / "bundles/solutions/ecommerce-growth/backend",
):
    if str(dependency) not in sys.path:
        sys.path.insert(0, str(dependency))

from ecommerce_growth.content_capability_runtime import ContentCapabilityRequest
from ecommerce_growth.sdk_ports import ExactRef


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

    def execute(self, query, params=()):
        compact = " ".join(query.split())
        if "FROM extension_operation_dispatch_binding" in compact:
            return Result(all_rows=deepcopy(self.dispatch_rows))
        if "FROM extension_runtime_binding" in compact:
            return Result(one=deepcopy(self.runtime_rows.get((params[-2], params[-1]))))
        if compact == "SELECT clock_timestamp() AS checked_at":
            return Result(one={"checked_at": datetime(2026, 9, 8, 8, tzinfo=UTC)})
        if compact == "SELECT %s AS written":
            return Result(one={"written": params[0]})
        raise AssertionError(compact)

    def commit(self):
        self.committed = True


def _fixture():
    installation, generation, group = uuid4(), uuid4(), uuid4()
    ref = SimpleNamespace(
        org_id="org-org",
        project_id="dev-project",
        operation_id="ecommerce_growth_case_put",
        handler_kind="extension",
        dispatch_revision=5,
        installation_id=str(installation),
        generation=str(generation),
        execution_epoch=7,
        cutover_group_id=str(group),
        cutover_group_revision=11,
    )
    dispatch_rows = [
        {
            "operation_id": ref.operation_id,
            "handler_kind": "extension",
            "installation_id": installation,
            "generation": generation,
            "execution_epoch": 7,
            "operation_fence": False,
            "revision": 5,
            "cutover_group_id": group,
            "cutover_group_revision": 11,
        },
        {
            "operation_id": "ecommerce_growth_schedule_put",
            "handler_kind": "extension",
            "installation_id": installation,
            "generation": generation,
            "execution_epoch": 7,
            "operation_fence": False,
            "revision": 4,
            "cutover_group_id": group,
            "cutover_group_revision": 11,
        },
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
    return ref, dispatch_rows, runtime_rows


def _factory(connection):
    @contextmanager
    def connect(_scope):
        yield connection

    return connect


def _binding(operation_id, executor=lambda **_: RECEIPT, *, authority_kinds=("case",),
             receipt_keys=("receiptRef",),
             revalidate=lambda **_: None, verify_receipt=lambda **kwargs: kwargs["receipt"]):
    return EcommerceGrowthOperationBinding(
        operation_id=operation_id,
        receipt_keys=receipt_keys,
        authority_kinds=authority_kinds,
        revalidate=revalidate,
        execute=executor,
        verify_receipt=verify_receipt,
    )


def test_host_revalidates_group_executes_and_returns_exact_receipt():
    ref, dispatch_rows, runtime_rows = _fixture()
    connection = FakeConnection(dispatch_rows, runtime_rows)
    source = {"businessTitle": "栖月汇经营分析", "input": {"range": "近30天"}}

    def executor(**kwargs):
        assert kwargs["scope"].key == ("org-org", "dev-project")
        assert kwargs["checked_at"] == datetime(2026, 9, 8, 8, tzinfo=UTC)
        assert kwargs["transaction"].execute("SELECT %s AS written", ("ok",)).fetchone() == {
            "written": "ok"
        }
        kwargs["command"]["input"]["range"] = "changed"
        return RECEIPT

    port = LockedEcommerceGrowthHostPort(
        {ref.operation_id: _binding(ref.operation_id, executor)}, connect_factory=_factory(connection)
    )
    assert port.commit(dispatch_ref=ref, command=source) == RECEIPT
    assert source["input"]["range"] == "近30天"
    assert connection.committed


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (lambda rows, runtime: rows[1].update(handler_kind="legacy", installation_id=None, generation=None,
                                               execution_epoch=None), EcommerceGrowthHostBlocked),
        (lambda rows, runtime: rows[0].update(revision=6), EcommerceGrowthHostConflict),
        (lambda rows, runtime: runtime[next(iter(runtime))].update(execution_epoch=8),
         EcommerceGrowthHostBlocked),
        (lambda rows, runtime: runtime[next(iter(runtime))].update(observed_state="draining", enabled=False,
                                                                  operation_fence=True),
         EcommerceGrowthHostBlocked),
    ],
)
def test_host_fails_closed_on_group_dispatch_or_runtime_drift(mutate, error):
    ref, dispatch_rows, runtime_rows = _fixture()
    mutate(dispatch_rows, runtime_rows)
    connection = FakeConnection(dispatch_rows, runtime_rows)
    port = LockedEcommerceGrowthHostPort({ref.operation_id: _binding(ref.operation_id)},
                                         connect_factory=_factory(connection))
    with pytest.raises(error):
        port.commit(dispatch_ref=ref, command={"businessTitle": "栖月汇"})
    assert not connection.committed


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("dispatch_revision", 4),
        ("generation", str(uuid4())),
        ("execution_epoch", 6),
        ("cutover_group_id", str(uuid4())),
        ("cutover_group_revision", 10),
    ],
)
def test_host_rejects_every_stale_exact_dispatch_dimension(field, value):
    ref, dispatch_rows, runtime_rows = _fixture()
    setattr(ref, field, value)
    connection = FakeConnection(dispatch_rows, runtime_rows)
    port = LockedEcommerceGrowthHostPort({ref.operation_id: _binding(ref.operation_id)},
                                         connect_factory=_factory(connection))
    with pytest.raises((EcommerceGrowthHostBlocked, EcommerceGrowthHostConflict)):
        port.commit(dispatch_ref=ref, command={})
    assert not connection.committed


@pytest.mark.parametrize(
    "command",
    [
        {"tenant": "dev-org"},
        {"nested": [{"dispatch_revision": 99}]},
        {"input": {"provider-url": "https://example.invalid"}},
        {"input": {"SQL": "delete from business"}},
        {"input": {"is_authorized": True}},
        {"input": {"source-access-authorized": True}},
    ],
)
def test_host_rejects_command_authority_overrides(command):
    ref, dispatch_rows, runtime_rows = _fixture()
    port = LockedEcommerceGrowthHostPort({ref.operation_id: _binding(ref.operation_id)},
                                         connect_factory=_factory(FakeConnection(dispatch_rows, runtime_rows)))
    with pytest.raises(ValueError, match="cannot override"):
        port.commit(dispatch_ref=ref, command=command)


@pytest.mark.parametrize(
    "command",
    [
        {"input": ({"tenant": "dev-org"},)},
        {"input": object()},
        {"value": float("nan")},
        {"value": float("inf")},
    ],
)
def test_host_rejects_non_json_command_tree(command):
    ref, dispatch_rows, runtime_rows = _fixture()
    port = LockedEcommerceGrowthHostPort({ref.operation_id: _binding(ref.operation_id)},
                                         connect_factory=_factory(FakeConnection(dispatch_rows, runtime_rows)))
    with pytest.raises(ValueError):
        port.commit(dispatch_ref=ref, command=command)


def test_host_rejects_async_or_inexact_executor_result():
    ref, dispatch_rows, runtime_rows = _fixture()

    async def async_executor(**_):
        return RECEIPT

    for executor in (async_executor, lambda **_: {"receiptRef": {"resourceType": "Case"}}):
        connection = FakeConnection(dispatch_rows, runtime_rows)
        port = LockedEcommerceGrowthHostPort(
            {ref.operation_id: _binding(ref.operation_id, executor)},
            connect_factory=_factory(connection),
        )
        with pytest.raises(EcommerceGrowthHostConflict):
            port.commit(dispatch_ref=ref, command={})
        assert not connection.committed


def test_host_rejects_missing_executor_and_wraps_executor_failure():
    ref, dispatch_rows, runtime_rows = _fixture()
    connection = FakeConnection(dispatch_rows, runtime_rows)
    with pytest.raises(EcommerceGrowthHostBlocked, match="no trusted host executor"):
        LockedEcommerceGrowthHostPort(
            {"ecommerce_growth_schedule_put": _binding("ecommerce_growth_schedule_put")},
            connect_factory=_factory(connection),
        ).commit(dispatch_ref=ref, command={})

    def failed_executor(**_):
        raise RuntimeError("internal database detail")

    with pytest.raises(EcommerceGrowthHostError, match="host transaction failed") as caught:
        LockedEcommerceGrowthHostPort(
            {ref.operation_id: _binding(ref.operation_id, failed_executor)},
            connect_factory=_factory(connection),
        ).commit(dispatch_ref=ref, command={})
    assert "internal database detail" not in str(caught.value)
    assert not connection.committed


def test_host_requires_current_authority_and_persisted_receipt_readback():
    ref, dispatch_rows, runtime_rows = _fixture()
    connection = FakeConnection(dispatch_rows, runtime_rows)

    def stale_authority(**_):
        raise EcommerceGrowthHostBlocked("business authority is not current")

    port = LockedEcommerceGrowthHostPort(
        {ref.operation_id: _binding(ref.operation_id, revalidate=stale_authority)},
        connect_factory=_factory(connection),
    )
    with pytest.raises(EcommerceGrowthHostBlocked, match="business authority"):
        port.commit(dispatch_ref=ref, command={})

    port = LockedEcommerceGrowthHostPort(
        {ref.operation_id: _binding(ref.operation_id, verify_receipt=lambda **_: {})},
        connect_factory=_factory(connection),
    )
    with pytest.raises(EcommerceGrowthHostConflict, match="readback drifted"):
        port.commit(dispatch_ref=ref, command={})
    assert not connection.committed


def test_production_composition_is_sealed_and_registration_only():
    registry = build_registration_only_ecommerce_growth_registry()
    assert registry.operation_ids == ECOMMERCE_GROWTH_OPERATIONS
    with pytest.raises(TypeError, match="host registry factory"):
        EcommerceGrowthHostAdapterRegistry({})
    with pytest.raises(TypeError, match="sealed adapter registry"):
        build_ecommerce_growth_host_ports({}, connect_factory=_factory(None))

    ref, dispatch_rows, runtime_rows = _fixture()
    ports = build_ecommerce_growth_host_ports(registry, connect_factory=_factory(
        FakeConnection(dispatch_rows, runtime_rows)
    ))
    assert set(ports.write_port._bindings) == {
        "ecommerce_growth_case_put",
        "ecommerce_growth_schedule_put",
    }
    assert set(ports.describe_port._bindings) == {"ecommerce_growth_investigation_describe"}
    route = {
        "ecommerce_growth_investigation_describe": "describe_port",
        "ecommerce_growth_case_put": "write_port",
        "ecommerce_growth_schedule_put": "write_port",
        "ecommerce_growth_schedule_trigger": "occurrence_port",
        "ecommerce_growth_data_fulfill": "data_port",
        "ecommerce_growth_analysis_advance": "runtime_port",
        "ecommerce_growth_review_advance": "review_port",
        "ecommerce_growth_content_generate": "capability_port",
        "ecommerce_growth_content_review": "content_review_port",
    }
    for operation_id in ECOMMERCE_GROWTH_OPERATIONS:
        current_ref, current_rows, current_runtime = _fixture()
        current_ref.operation_id = operation_id
        current_rows[0]["operation_id"] = operation_id
        current_ports = build_ecommerce_growth_host_ports(
            registry,
            connect_factory=_factory(FakeConnection(current_rows, current_runtime)),
        )
        with pytest.raises(EcommerceGrowthHostBlocked, match="AR2_7D_RUNTIME_WIRING_REQUIRED"):
            getattr(current_ports, route[operation_id]).commit(
                dispatch_ref=current_ref,
                command={"businessTitle": "栖月汇经营分析"},
            )


def test_real_n7_command_allows_approval_ref_but_rejects_claimed_approval():
    exact = lambda kind, identity: ExactRef(kind, identity, 1, "sha256:" + "a" * 64)
    request = ContentCapabilityRequest(
        handoff_ref=exact("HandoffReceipt", "handoff-1"),
        task_ref=exact("Task", "task-1"),
        brief_ref=exact("TaskBriefRevision", "brief-1"),
        growth_plan_ref=exact("GrowthPlanRevision", "plan-1"),
        source_artifact_refs=tuple(
            exact("ArtifactRevision", f"source-{index}") for index in range(4)
        ),
        fact_source_refs=(exact("DataFulfillmentReceipt", "fulfillment-1"),),
        agent_instance_ref=exact("AgentInstanceRevision", "agent-1"),
        responsibility_plan_ref=exact("ResponsibilityPlanRevision", "responsibility-1"),
        capability_ref=exact("CapabilityRevision", "capability-1"),
        model_route_ref=exact("ModelRouteRevision", "route-1"),
        budget_ref=exact("BudgetRevision", "budget-1"),
        pricing_ref=exact("ModelPriceSnapshotRevision", "price-1"),
        approval_ref=exact("ActionApprovalEvent", "approval-1"),
        capacity_reservation_ref=exact("CapacityReservation", "capacity-1"),
        currency="CNY",
        upper_bound_fen=500,
        max_input_tokens=4_000,
        max_output_tokens=2_000,
        idempotency_key="n7-host-command-1",
    )
    ref, dispatch_rows, runtime_rows = _fixture()
    ref.operation_id = "ecommerce_growth_content_generate"
    dispatch_rows[0]["operation_id"] = ref.operation_id
    port = LockedEcommerceGrowthHostPort(
        {ref.operation_id: _binding(ref.operation_id)},
        connect_factory=_factory(FakeConnection(dispatch_rows, runtime_rows)),
    )
    assert port.commit(dispatch_ref=ref, command=request.command_payload()) == RECEIPT
    with pytest.raises(ValueError, match="cannot override"):
        port.commit(dispatch_ref=ref, command={**request.command_payload(), "approved": True})
