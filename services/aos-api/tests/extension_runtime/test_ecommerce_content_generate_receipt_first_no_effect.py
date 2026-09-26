from types import SimpleNamespace

import pytest

from aos_api.aip_budget_reservation_contracts import (
    BudgetExactRef,
    BudgetReservationState,
)
from aos_api.ecommerce_growth_runtime_adapters import (
    ContentGenerateAdapter,
    ContentGenerateHostService,
    ReviewAdvanceHostService,
    _analysis_command_hash,
)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_store import RuntimeReceiptRecord


def _ref(kind: str, identity: str) -> dict[str, object]:
    return {
        "resourceType": kind,
        "resourceId": identity,
        "revision": 1,
        "contentHash": "sha256:" + identity[0] * 64,
    }


def _command() -> dict[str, object]:
    kinds = {
        "handoff": "HandoffReceipt",
        "task": "Task",
        "brief": "TaskBriefRevision",
        "growth_plan": "GrowthPlanRevision",
        "agent_instance": "AgentInstanceRevision",
        "responsibility_plan": "ResponsibilityPlanRevision",
        "capability": "CapabilityRevision",
        "model_route": "ModelRouteRevision",
        "budget": "BudgetRevision",
        "pricing": "ModelPriceSnapshotRevision",
        "approval": "ActionApprovalEvent",
        "capacity_reservation": "CapacityReservation",
    }
    payload = {
        "operation": "content.generate",
        "authorityRefs": {
            name: _ref(kind, hex(index + 1)[2:])
            for index, (name, kind) in enumerate(kinds.items())
        },
        "sourceArtifactRefs": [
            _ref("ArtifactRevision", value) for value in ("a", "b", "c", "d")
        ],
        "factSourceRefs": [_ref("EvidenceBundleRevision", "e")],
        "currency": "CNY",
        "upperBoundFen": 400,
        "maxInputTokens": 1000,
        "maxOutputTokens": 500,
        "idempotencyKey": "content-no-effect-1",
    }
    payload["requestHash"] = _analysis_command_hash(payload)
    return payload


def _budget_ref(kind: str, identity: str, digit: str) -> BudgetExactRef:
    return BudgetExactRef(
        resourceType=kind,
        resourceId=identity,
        revision=2,
        contentHash="sha256:" + digit * 64,
    )


def _reservation(command, *, state=BudgetReservationState.RELEASED, replayed=False):
    request = ContentGenerateHostService._budget_request(command)
    return SimpleNamespace(
        state=state,
        invocation_ref=_budget_ref("CapabilityInvocationRevision", "invocation-1", "7"),
        reservation_ref=_budget_ref("BudgetReservationRevision", "reservation-1", "8"),
        operation_id=request.operation_id,
        invocation_key=request.invocation_key,
        task_ref=request.task_ref,
        policy_ref=request.policy_ref,
        pricing_ref=request.pricing_ref,
        approval_ref=request.approval_ref,
        currency=request.currency,
        upper_bound_minor=request.upper_bound_minor,
        request_hash=request.request_hash(),
        provider_request_receipt_ref=None,
        provider_receipt_ref=None,
        usage_receipt_refs=(),
        actual_minor=None,
        reconciliation_evidence_ref=None,
        replayed=replayed,
    )


class _Store:
    def __init__(self, command, *, reserve_state=BudgetReservationState.HELD):
        self.command = command
        self.reserve_state = reserve_state
        self.released = _reservation(command)
        self.calls = []

    def reserve(self, scope, request, *, actor):
        self.calls.append(("reserve", scope, request, actor))
        return _reservation(self.command, state=self.reserve_state)

    def release_no_effect(self, scope, reservation_id, *, actor):
        self.calls.append(("release", scope, reservation_id, actor))
        return self.released

    def get(self, scope, reservation_id):
        self.calls.append(("get", scope, reservation_id))
        return self.released


def _plan(monkeypatch, *, v2=False):
    monkeypatch.setattr(
        ReviewAdvanceHostService, "_revalidate_growth_plan",
        staticmethod(lambda **_: SimpleNamespace(sales_weapon_method=object() if v2 else None)),
    )


def test_execute_reserves_before_releasing_and_returns_strict_no_effect(monkeypatch):
    _plan(monkeypatch)
    command = _command()
    store = _Store(command)
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_budget_store",
        staticmethod(lambda _transaction, _scope: store),
    )
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_runtime_command_authority",
        staticmethod(lambda *_args: None),
    )
    service = ContentGenerateHostService()
    result = service.execute(
        transaction=object(),
        scope=object(),
        dispatch_ref=object(),
        command=command,
        checked_at=None,
        occurred_at=None,
    )

    assert [call[0] for call in store.calls] == ["reserve", "release"]
    assert result["state"] == "FAILED_NO_EFFECT"
    assert result["budgetState"] == "RELEASED"
    assert result["retryDirective"] == "RETRYABLE_NO_EFFECT"
    assert result["sideEffects"] == {
        "providerInvocationCount": 0,
        "approvalCreatedCount": 0,
        "taskRunCreatedCount": 0,
        "externalPublicationCount": 0,
        "externalBusinessMutationCount": 0,
    }
    assert result["providerRequestReceiptRef"] is None
    assert result["providerReceiptRef"] is None
    assert result["usageReceiptRefs"] == []
    assert result["artifact"] is None
    assert service.verify_receipt(
        transaction=object(), scope=object(), dispatch=object(), command=command, receipt=result
    ) == result


def test_execute_rejects_an_invocation_that_crossed_provider_boundary(monkeypatch):
    _plan(monkeypatch)
    command = _command()
    store = _Store(command, reserve_state=BudgetReservationState.SUBMITTED)
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_budget_store",
        staticmethod(lambda _transaction, _scope: store),
    )
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_runtime_command_authority",
        staticmethod(lambda *_args: None),
    )

    with pytest.raises(ValueError, match="crossed Provider boundary"):
        ContentGenerateHostService().execute(
            transaction=object(),
            scope=object(),
            dispatch_ref=object(),
            command=command,
            checked_at=None,
            occurred_at=None,
        )
    assert [call[0] for call in store.calls] == ["reserve"]


def test_v2_execute_persists_pending_command_without_provider_or_release(monkeypatch):
    _plan(monkeypatch, v2=True)
    command = _command()
    store = _Store(command)
    observed = []
    monkeypatch.setattr(ContentGenerateHostService, "_budget_store",
                        staticmethod(lambda *_: store))
    monkeypatch.setattr(ContentGenerateHostService, "_runtime_command_authority",
                        staticmethod(lambda *_: None))
    monkeypatch.setattr(HostTransaction, "enqueue_content_command",
                        lambda self, **kwargs: observed.append(kwargs) or kwargs["command"])
    monkeypatch.setattr(HostTransaction, "read_content_command",
                        lambda self, **kwargs: {"command": command, "result": None})
    transaction = HostTransaction(object())
    service = ContentGenerateHostService()
    receipt = service.execute(transaction=transaction, scope=object(), dispatch_ref=object(),
                              command=command, checked_at=None, occurred_at=None)
    assert receipt["state"] == "PENDING" and receipt["budgetState"] == "HELD"
    assert receipt["sideEffects"]["providerInvocationCount"] == 0
    assert [call[0] for call in store.calls] == ["reserve"]
    assert observed[0]["budget_request_hash"] == service._budget_request(command).request_hash()
    assert observed[0]["command"] == command
    assert service.verify_receipt(transaction=transaction, scope=object(), dispatch=None,
                                  command=command, receipt=receipt) == receipt
    # A later budget state must not reclassify the immutable acceptance as completion.
    assert store.released.state is BudgetReservationState.RELEASED
    drift = {**receipt, "providerRequestReceiptRef": _ref("CapabilityProviderRequestReceipt", "a")}
    assert service.verify_receipt(transaction=transaction, scope=object(), dispatch=None,
                                  command=command, receipt=drift) == {}


def test_v2_execute_does_not_release_when_durable_enqueue_fails(monkeypatch):
    _plan(monkeypatch, v2=True)
    command = _command()
    store = _Store(command)
    monkeypatch.setattr(ContentGenerateHostService, "_budget_store", staticmethod(lambda *_: store))
    monkeypatch.setattr(ContentGenerateHostService, "_runtime_command_authority",
                        staticmethod(lambda *_: None))
    def failed_enqueue(self, **kwargs):
        raise RuntimeError("journal unavailable")
    monkeypatch.setattr(HostTransaction, "enqueue_content_command", failed_enqueue)
    with pytest.raises(RuntimeError, match="journal unavailable"):
        ContentGenerateHostService().execute(
            transaction=HostTransaction(object()), scope=object(), dispatch_ref=object(),
            command=command, checked_at=None, occurred_at=None,
        )
    assert [call[0] for call in store.calls] == ["reserve"]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("state",), "COMPLETED"),
        (("budgetState",), "HELD"),
        (("replayed",), 1),
        (("sideEffects", "providerInvocationCount"), 1),
        (("authorityRefs", "task", "revision"), True),
        (("budgetReservationRef", "contentHash"), "sha256:" + "9" * 64),
    ],
)
def test_verify_rejects_receipt_or_exact_ref_drift(monkeypatch, path, value):
    command = _command()
    store = _Store(command)
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_budget_store",
        staticmethod(lambda _transaction, _scope: store),
    )
    receipt = ContentGenerateHostService._no_effect_receipt(
        command, store.released, replayed=False
    )
    target = receipt
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    assert ContentGenerateHostService().verify_receipt(
        transaction=object(), scope=object(), dispatch=object(), command=command, receipt=receipt
    ) == {}


def test_runtime_command_authority_rejects_full_command_hash_drift():
    command = _command()

    class _Result:
        def __init__(self, row):
            self.row = row

        def fetchone(self):
            return self.row

    class _Transaction:
        def __init__(self, row):
            self.row = row
            self.calls = []

        def execute(self, query, params):
            self.calls.append((query, params))
            return _Result(self.row)

    scope = SimpleNamespace(key=("org-org", "dev-project"))
    transaction = _Transaction(
        {
            "request_hash": "sha256:" + "0" * 64,
            "response": {"requestHash": command["requestHash"]},
        }
    )
    with pytest.raises(ValueError, match="full command replay drifted"):
        ContentGenerateHostService._runtime_command_authority(
            transaction, scope, command
        )
    assert "public.ecommerce_growth_runtime_command_receipt" in transaction.calls[0][0]


def test_adapter_journal_replay_keeps_first_persisted_receipt(monkeypatch):
    _plan(monkeypatch)
    command = _command()
    store = _Store(command)

    class _Journal:
        saved = None

        def __init__(self, _transaction, _scope):
            pass

        def put(self, **kwargs):
            if self.__class__.saved is None:
                self.__class__.saved = kwargs["response"]
            assert kwargs["response"] == self.__class__.saved
            return RuntimeReceiptRecord(
                response=self.__class__.saved,
                replayed=self.__class__.saved is not kwargs["response"],
            )

    monkeypatch.setattr(
        ContentGenerateHostService,
        "_budget_store",
        staticmethod(lambda _transaction, _scope: store),
    )
    monkeypatch.setattr(
        ContentGenerateHostService,
        "_runtime_command_authority",
        staticmethod(lambda *_args: _Journal.saved),
    )
    monkeypatch.setattr(
        "aos_api.ecommerce_growth_runtime_adapters.BoundEcommerceGrowthRuntimeStore",
        _Journal,
    )
    binding = ContentGenerateAdapter(ContentGenerateHostService()).binding()
    common = {
        "transaction": object(),
        "scope": object(),
        "dispatch_ref": object(),
        "command": command,
        "checked_at": None,
        "occurred_at": None,
    }
    first = binding.execute(**common)
    persisted_first = binding.verify_receipt(
        transaction=object(),
        scope=object(),
        dispatch=SimpleNamespace(checked_at=None),
        command=command,
        receipt=first,
    )
    second = binding.execute(**common)
    persisted_second = binding.verify_receipt(
        transaction=object(),
        scope=object(),
        dispatch=SimpleNamespace(checked_at=None),
        command=command,
        receipt=second,
    )
    assert persisted_first == persisted_second == first
    assert first["replayed"] is False
    assert [call[0] for call in store.calls] == ["reserve", "release", "get", "get", "get"]
