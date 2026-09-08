from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from aos_api.ecommerce_growth_host_composition import (
    ECOMMERCE_GROWTH_AUTHORITY_KINDS,
    ECOMMERCE_GROWTH_OPERATIONS,
    ECOMMERCE_GROWTH_RECEIPT_KEYS,
)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import (
    RUNTIME_ADAPTER_TYPES,
    TransactionBoundConnectFactory,
)
from aos_api.tenant_scope import TenantScope
import aos_api.ecommerce_growth_runtime_adapters as runtime_adapters


class DomainService:
    executor_identity = "ecommerce-growth-runtime"

    def revalidate(self, **_):
        return None

    def execute(self, **_):
        raise AssertionError("not part of adapter construction")

    def verify_receipt(self, **kwargs):
        return kwargs["receipt"]


def test_nine_explicit_adapter_specs_match_the_sealed_host_registry():
    bindings = tuple(adapter(DomainService()).binding() for adapter in RUNTIME_ADAPTER_TYPES)
    assert tuple(binding.operation_id for binding in bindings) == ECOMMERCE_GROWTH_OPERATIONS
    assert all(binding.authority_kinds == ECOMMERCE_GROWTH_AUTHORITY_KINDS[binding.operation_id] for binding in bindings)
    assert all(binding.receipt_keys == ECOMMERCE_GROWTH_RECEIPT_KEYS[binding.operation_id] for binding in bindings)
    assert len({type(adapter).__name__ for adapter in (kind(DomainService()) for kind in RUNTIME_ADAPTER_TYPES)}) == 9


@pytest.mark.parametrize("missing", ["identity", "revalidate", "execute", "verify_receipt"])
def test_adapter_rejects_untrusted_or_incomplete_domain_service(missing):
    service = DomainService()
    if missing == "identity":
        service.executor_identity = ""
    else:
        setattr(service, missing, None)
    with pytest.raises(TypeError):
        RUNTIME_ADAPTER_TYPES[0](service)


def test_host_receipt_verifier_contract_includes_original_command():
    binding = RUNTIME_ADAPTER_TYPES[0](DomainService()).binding()
    assert binding.operation_id == "ecommerce_growth_investigation_describe"
    # The actual persistence path is covered by runtime-store tests and the PG suite;
    # this assertion guards the command-aware callback introduced for exact replay.
    assert binding.verify_receipt.__name__ == "_verify_and_journal"


def test_transaction_bound_store_connection_cannot_commit_rollback_or_cross_scope():
    executed = []

    class Connection:
        def execute(self, query, params):
            executed.append((query, params))
            return "cursor"

    scope = TenantScope("org-org", "dev-project")
    factory = TransactionBoundConnectFactory(HostTransaction(Connection()), scope)
    with factory(scope) as conn:
        assert conn.execute("SELECT 1", ("经营参谋",)) == "cursor"
        assert conn.commit() is None
        with pytest.raises(RuntimeError, match="cannot roll back"):
            conn.rollback()
    assert executed == [("SELECT 1", ("经营参谋",))]
    with pytest.raises(PermissionError, match="different tenant"):
        with factory(TenantScope("dev-org", "dev-project")):
            pass


def exact(kind, identity):
    return {
        "resourceType": kind,
        "resourceId": identity,
        "revision": 1,
        "contentHash": "sha256:" + "a" * 64,
    }


def case_command():
    return {
        "idempotencyKey": "case-qyh-001",
        "taskBriefRef": exact("TaskBriefRevision", "brief-qyh-001"),
        "case": {
            "caseId": "case-qyh-001",
            "analysisType": "initial_store_analysis",
            "title": "栖月汇微商城首次经营分析",
            "purposeCode": "initial.store.analysis",
            "channelRef": exact("ChannelRevision", "niushop:1"),
            "businessEntityRef": exact("BusinessEntityRevision", "shop-1"),
            "entityChannelBindingRef": exact(
                "BusinessEntityChannelBindingRevision", "niushop:1:shop-1"
            ),
            "investigationProfileRef": exact(
                "InvestigationProfileRevision", "initial-store-analysis"
            ),
            "scopeRef": exact("InvestigationScopeRevision", "whole-store"),
        },
    }


def schedule_put_command():
    return {
        "idempotencyKey": "schedule-qyh-001",
        "caseId": "case-qyh-001",
        "expectedPolicyRevision": 0,
        "expectedCaseVersion": 1,
        "policy": {
            "schedulePolicyId": "schedule-qyh-001",
            "caseRef": exact("BusinessInvestigationCaseRevision", "case-qyh-001"),
            "analysisType": "initial_store_analysis",
            "policyKind": "initial_checkup",
            "cadence": "once",
            "enabled": True,
            "overlapPolicy": "skip",
            "timezone": "Asia/Shanghai",
        },
        "approvalRef": exact("ActionApprovalEvent", "approval-qyh-001"),
    }


def schedule_trigger_command():
    return {
        "idempotencyKey": "occurrence-qyh-001",
        "schedulePolicyRef": {
            "resourceType": "SchedulePolicyRevision",
            "resourceId": "schedule-qyh-001",
            "revision": 1,
            "contentHash": "sha256:" + "b" * 64,
        },
        "scheduledAt": "2026-09-08T12:00:00Z",
        "localSlot": "2026-09-08T20:00+0800",
        "deadline": "2026-09-09T12:00:00Z",
    }


def test_case_host_service_rejects_authority_override_and_revalidates_exact_selection(monkeypatch):
    command = case_command()
    scope = TenantScope("org-org", "dev-project")
    refs = command["case"]

    class Cursor:
        def fetchall(self):
            return [{"external_id": "shop-1"}]

        def fetchone(self):
            return {"current_revision": 1}

    class Connection:
        def execute(self, *_):
            return Cursor()

    class Shops:
        def __init__(self, _factory):
            pass

        def read(self, _scope):
            return SimpleNamespace(
                channel_ref=runtime_adapters.InvestigationExactRef.model_validate(refs["channelRef"]),
                business_entity_ref=runtime_adapters.InvestigationExactRef.model_validate(
                    refs["businessEntityRef"]
                ),
                entity_channel_binding_ref=runtime_adapters.InvestigationExactRef.model_validate(
                    refs["entityChannelBindingRef"]
                ),
            )

    class Composition:
        def __init__(self, _factory):
            pass

    class Profiles:
        def __init__(self, *, composition_source):
            assert isinstance(composition_source, Composition)

        def read(self, _scope, _analysis_type):
            return SimpleNamespace(
                investigation_profile_ref=runtime_adapters.InvestigationExactRef.model_validate(
                    refs["investigationProfileRef"]
                ),
                scope_ref=runtime_adapters.InvestigationExactRef.model_validate(refs["scopeRef"]),
            )

    class Briefs:
        def __init__(self, _factory):
            pass

        def get_brief(self, *_args, **_kwargs):
            return SimpleNamespace(content_hash="a" * 64, lifecycle=SimpleNamespace(value="frozen"))

    monkeypatch.setattr(runtime_adapters, "PostgresCanonicalShopSelectionSource", Shops)
    monkeypatch.setattr(runtime_adapters, "PostgresAipProductionCompositionSource", Composition)
    monkeypatch.setattr(runtime_adapters, "CatalogCanonicalProfileSelectionSource", Profiles)
    monkeypatch.setattr(runtime_adapters, "AipProductionContractStore", Briefs)
    service = runtime_adapters.CasePutHostService()
    service.revalidate(
        transaction=HostTransaction(Connection()), scope=scope, dispatch=None, command=command
    )
    with pytest.raises(ValueError, match="exactly"):
        service.revalidate(
            transaction=HostTransaction(Connection()),
            scope=scope,
            dispatch=None,
            command={**command, "tenant": {"orgId": "org-org"}},
        )


def test_case_host_service_returns_and_rereads_exact_case_authority(monkeypatch):
    command = case_command()
    scope = TenantScope("org-org", "dev-project")
    authority_payload = {
        **command["case"],
        "schemaVersion": "aos.ecommerce.business-investigation-case/v1",
        "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
        "revision": 1,
        "version": 1,
        "contentHash": "sha256:" + "b" * 64,
        "lifecycle": "DRAFT",
        "createdBy": "ecommerce-growth-case-host",
        "createdAt": "2026-09-08T12:00:00Z",
    }
    authority = SimpleNamespace(
        case_id="case-qyh-001",
        revision=1,
        content_hash="sha256:" + "b" * 64,
        enabled=True,
        model_dump=lambda **_: authority_payload,
    )

    class Cases:
        def __init__(self, _factory):
            pass

        def get(self, _scope, _case_id):
            return authority

    class App:
        def __init__(self, *, case_store, case_selection_resolver):
            assert isinstance(case_store, Cases)

        def create_case(self, *_args, **_kwargs):
            return SimpleNamespace(authority=authority, replayed=False)

    monkeypatch.setattr(runtime_adapters, "BusinessInvestigationCaseStore", Cases)
    monkeypatch.setattr(runtime_adapters, "EcommerceBusinessInvestigationApplication", App)
    service = runtime_adapters.CasePutHostService()
    transaction = HostTransaction(SimpleNamespace(execute=lambda *_: None))
    response = service.execute(
        transaction=transaction,
        scope=scope,
        dispatch_ref=None,
        command=command,
        checked_at=datetime(2026, 9, 8, 12, tzinfo=UTC),
        occurred_at=None,
    )
    assert response["receiptRef"]["resourceId"] == "case-qyh-001"
    assert service.verify_receipt(
        transaction=transaction,
        scope=scope,
        dispatch=None,
        command=command,
        receipt=response,
    ) == response


def test_schedule_put_revalidates_case_policy_and_exact_approval(monkeypatch):
    command = schedule_put_command()
    scope = TenantScope("org-org", "dev-project")
    checked_at = datetime(2026, 9, 8, 12, tzinfo=UTC)
    approval_row = {
        "approval_event_id": "approval-qyh-001",
        "proposal_id": "proposal-qyh-001",
        "proposal_version": 1,
        "proposal_hash": "proposal-hash",
        "decision": "approved",
        "actor_id": "operator-qyh",
        "reason": "批准首次经营分析周期计划",
        "expires_at": datetime(2026, 9, 9, 12, tzinfo=UTC),
        "created_at": checked_at,
        "action_binding_hash": "binding-hash",
    }
    command["approvalRef"]["contentHash"] = runtime_adapters.budget_canonical_hash(
        approval_row, prefixed=True
    )
    proposal_row = {
        "proposal_id": "proposal-qyh-001",
        "action_type_id": "ecommerce_growth_schedule_put",
        "payload": {
            "caseId": "case-qyh-001",
            "schedulePolicyId": "schedule-qyh-001",
            "expectedPolicyRevision": 0,
            "expectedCaseVersion": 1,
        },
        "proposal_hash": "proposal-hash",
        "status": "approved",
        "action_binding_hash": "binding-hash",
    }

    class Cursor:
        def __init__(self, row):
            self.row = row

        def fetchone(self):
            return self.row

    class Connection:
        def execute(self, sql, _params):
            if "case_head" in sql:
                return Cursor({"current_revision": 1})
            if "schedule_policy_head" in sql:
                return Cursor(None)
            if "aip_action_approval_event" in sql:
                return Cursor(approval_row)
            if "aip_action_proposal" in sql:
                return Cursor(proposal_row)
            raise AssertionError(sql)

    class Cases:
        def __init__(self, _factory):
            pass

        def get(self, _scope, _case_id):
            return SimpleNamespace(
                content_hash="sha256:" + "a" * 64,
                analysis_type=runtime_adapters.PutBusinessInvestigationSchedulePolicyRequest.model_validate(
                    command["policy"]
                ).analysis_type,
            )

    monkeypatch.setattr(runtime_adapters, "BusinessInvestigationCaseStore", Cases)
    service = runtime_adapters.SchedulePutHostService()
    dispatch = SimpleNamespace(checked_at=checked_at)
    service.revalidate(
        transaction=HostTransaction(Connection()), scope=scope, dispatch=dispatch, command=command
    )
    drifted = {**command, "expectedCaseVersion": 2}
    with pytest.raises(ValueError, match="Case authority"):
        service.revalidate(
            transaction=HostTransaction(Connection()), scope=scope, dispatch=dispatch, command=drifted
        )
    with pytest.raises(ValueError, match="invalid envelope"):
        service.revalidate(
            transaction=HostTransaction(Connection()),
            scope=scope,
            dispatch=dispatch,
            command={**command, "current": True},
        )


def test_schedule_put_returns_and_rereads_policy_and_case(monkeypatch):
    command = schedule_put_command()
    scope = TenantScope("org-org", "dev-project")
    authority = SimpleNamespace(
        schedule_policy_id="schedule-qyh-001",
        revision=1,
        content_hash="sha256:" + "b" * 64,
        enabled=True,
        model_dump=lambda **_: {"schedulePolicyId": "schedule-qyh-001", "revision": 1},
    )
    case = SimpleNamespace(
        model_dump=lambda **_: {"caseId": "case-qyh-001", "revision": 2}
    )

    class Schedules:
        def __init__(self, _factory):
            pass

        def get(self, _scope, _policy_id):
            return authority

    class Cases:
        def __init__(self, _factory):
            pass

        def get(self, _scope, _case_id):
            return case

    class App:
        def __init__(self, *, case_store, schedule_store):
            assert isinstance(case_store, Cases) and isinstance(schedule_store, Schedules)

        def put_schedule_policy(self, *_args, **_kwargs):
            return SimpleNamespace(authority=authority, case_authority=case, replayed=False)

    class Occurrences:
        def __init__(self, _factory):
            pass

        def disable_policy_bindings(self, _scope, _policy_id, *, keep_revision):
            assert keep_revision == 1

    monkeypatch.setattr(runtime_adapters, "BusinessInvestigationScheduleStore", Schedules)
    monkeypatch.setattr(runtime_adapters, "BusinessInvestigationCaseStore", Cases)
    monkeypatch.setattr(runtime_adapters, "EcommerceBusinessInvestigationApplication", App)
    monkeypatch.setattr(runtime_adapters, "AutomationOccurrenceStore", Occurrences)
    service = runtime_adapters.SchedulePutHostService()
    transaction = HostTransaction(SimpleNamespace(execute=lambda *_: None))
    response = service.execute(
        transaction=transaction,
        scope=scope,
        dispatch_ref=None,
        command=command,
        checked_at=datetime(2026, 9, 8, 12, tzinfo=UTC),
        occurred_at=None,
    )
    assert response["receiptRef"]["resourceId"] == "schedule-qyh-001"
    assert service.verify_receipt(
        transaction=transaction,
        scope=scope,
        dispatch=None,
        command=command,
        receipt=response,
    ) == response


def test_schedule_trigger_revalidates_exact_enabled_policy(monkeypatch):
    command = schedule_trigger_command()
    scope = TenantScope("org-org", "dev-project")
    policy = SimpleNamespace(
        schedule_policy_id="schedule-qyh-001",
        revision=1,
        content_hash="sha256:" + "b" * 64,
        enabled=True,
        cadence=SimpleNamespace(value="once"),
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        model_dump=lambda **_: command["schedulePolicyRef"],
    )

    class Schedules:
        def __init__(self, _factory):
            pass

        def get(self, _scope, _policy_id):
            return policy

    class Cursor:
        def fetchone(self):
            return {"current_revision": 1}

    monkeypatch.setattr(runtime_adapters, "BusinessInvestigationScheduleStore", Schedules)
    service = runtime_adapters.ScheduleTriggerHostService()
    service.revalidate(
        transaction=HostTransaction(SimpleNamespace(execute=lambda *_: Cursor())),
        scope=scope,
        dispatch=SimpleNamespace(
            operation_id="ecommerce_growth_schedule_trigger",
            execution_epoch=3,
            checked_at=datetime(2026, 9, 8, 12, tzinfo=UTC),
        ),
        command=command,
    )
    with pytest.raises(ValueError, match="natural slot"):
        service.revalidate(
            transaction=HostTransaction(SimpleNamespace(execute=lambda *_: Cursor())),
            scope=scope,
            dispatch=SimpleNamespace(
                operation_id="ecommerce_growth_schedule_trigger",
                execution_epoch=3,
                checked_at=datetime(2026, 9, 8, 12, tzinfo=UTC),
            ),
            command={**command, "localSlot": "not-the-shanghai-slot"},
        )
    with pytest.raises(ValueError, match="future slot"):
        service.revalidate(
            transaction=HostTransaction(SimpleNamespace(execute=lambda *_: Cursor())),
            scope=scope,
            dispatch=SimpleNamespace(
                operation_id="ecommerce_growth_schedule_trigger",
                execution_epoch=3,
                checked_at=datetime(2026, 9, 8, 12, tzinfo=UTC),
            ),
            command={
                **command,
                "scheduledAt": "2026-09-09T12:00:00Z",
                "localSlot": "2026-09-09T20:00+0800",
                "deadline": "2026-09-10T12:00:00Z",
            },
        )
    with pytest.raises(ValueError, match="outside the bounded recovery window"):
        service.revalidate(
            transaction=HostTransaction(SimpleNamespace(execute=lambda *_: Cursor())),
            scope=scope,
            dispatch=SimpleNamespace(
                operation_id="ecommerce_growth_schedule_trigger",
                execution_epoch=3,
                checked_at=datetime(2026, 9, 8, 12, tzinfo=UTC),
            ),
            command={
                **command,
                "scheduledAt": "2026-09-06T12:00:00Z",
                "localSlot": "2026-09-06T20:00+0800",
            },
        )
    within_window = {
        **command,
        "scheduledAt": "2026-09-07T13:00:00Z",
        "localSlot": "2026-09-07T21:00+0800",
    }
    service.revalidate(
        transaction=HostTransaction(SimpleNamespace(execute=lambda *_: Cursor())),
        scope=scope,
        dispatch=SimpleNamespace(
            operation_id="ecommerce_growth_schedule_trigger",
            execution_epoch=3,
            checked_at=datetime(2026, 9, 8, 12, tzinfo=UTC),
        ),
        command=within_window,
    )
    with pytest.raises(ValueError, match="invalid envelope"):
        service.revalidate(
            transaction=HostTransaction(SimpleNamespace(execute=lambda *_: Cursor())),
            scope=scope,
            dispatch=SimpleNamespace(
                operation_id="ecommerce_growth_schedule_trigger",
                execution_epoch=3,
                checked_at=datetime(2026, 9, 8, 12, tzinfo=UTC),
            ),
            command={**command, "enabled": True},
        )


def test_schedule_trigger_writes_unique_occurrence_and_exact_readback(monkeypatch):
    command = schedule_trigger_command()
    scope = TenantScope("org-org", "dev-project")
    installation = UUID("11111111-1111-4111-8111-111111111111")
    generation = UUID("22222222-2222-4222-8222-222222222222")
    occurrence = UUID("33333333-3333-4333-8333-333333333333")
    policy = SimpleNamespace(
        schedule_policy_id="schedule-qyh-001",
        revision=1,
        content_hash="sha256:" + "b" * 64,
        cadence=SimpleNamespace(value="once"),
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        weekly_day=None,
        local_time=None,
    )
    row = {
        "occurrence_id": occurrence,
        "policy_id": "schedule-qyh-001",
        "policy_revision": 1,
        "policy_hash": "sha256:" + "b" * 64,
        "operation_id": "ecommerce_growth_schedule_trigger",
        "installation_id": installation,
        "generation": generation,
        "execution_epoch": 3,
        "scheduled_at": datetime(2026, 9, 8, 12, tzinfo=UTC),
        "local_slot": "2026-09-08T20:00+0800",
        "trigger_source": "schedule",
        "source_event_id": None,
        "status": "pending",
        "deadline": datetime(2026, 9, 9, 12, tzinfo=UTC),
    }

    class Cursor:
        def fetchone(self):
            return row

    class Schedules:
        def __init__(self, _factory):
            pass

        def get(self, _scope, _policy_id):
            return policy

    class Occurrences:
        def __init__(self, _factory):
            pass

        def put_binding(self, _scope, binding):
            assert binding.execution_epoch == 3 and binding.enabled

        def record_scheduled(self, _scope, _binding, **kwargs):
            assert kwargs["scheduled_at"] == row["scheduled_at"]
            return SimpleNamespace(occurrence_id=occurrence, status="pending", replayed=False)

    monkeypatch.setattr(runtime_adapters, "BusinessInvestigationScheduleStore", Schedules)
    monkeypatch.setattr(runtime_adapters, "AutomationOccurrenceStore", Occurrences)
    transaction = HostTransaction(SimpleNamespace(execute=lambda *_: Cursor()))
    dispatch = SimpleNamespace(
        operation_id="ecommerce_growth_schedule_trigger",
        installation_id=installation,
        generation=generation,
        execution_epoch=3,
    )
    service = runtime_adapters.ScheduleTriggerHostService()
    response = service.execute(
        transaction=transaction,
        scope=scope,
        dispatch_ref=dispatch,
        command=command,
        checked_at=datetime(2026, 9, 8, 12, tzinfo=UTC),
        occurred_at=None,
    )
    assert response["occurrenceRef"]["resourceId"] == str(occurrence)
    assert service.verify_receipt(
        transaction=transaction,
        scope=scope,
        dispatch=dispatch,
        command=command,
        receipt=response,
    ) == response
    assert service.verify_receipt(
        transaction=transaction,
        scope=scope,
        dispatch=dispatch,
        command=command,
        receipt={**response, "status": "accepted"},
    ) == {}
