from datetime import UTC, datetime
from types import SimpleNamespace

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
