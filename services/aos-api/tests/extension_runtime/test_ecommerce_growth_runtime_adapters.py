from datetime import UTC, datetime

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
