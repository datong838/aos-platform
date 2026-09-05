"""R5-M02 canonical media-studio source reader tests."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from aos_api.ecommerce_workshop_media_studio_contracts import MediaReadinessAxis
from aos_api.ecommerce_workshop_media_studio_reader import MediaStudioReadError
from aos_api.ecommerce_workshop_media_studio_source_reader import (
    EcommerceWorkshopMediaStudioSourceReader,
)
from aos_api.tenant_scope import TenantScope


CUTOFF = datetime(2026, 9, 5, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")


def result(items):
    return SimpleNamespace(items=items)


class ProductionStore:
    def __init__(self, *, contexts=(), families=(), gates=(), issues=(), returns=()):
        self.contexts = list(contexts)
        self.families = list(families)
        self.gates = list(gates)
        self.issues = list(issues)
        self.returns = list(returns)

    def list_production_contexts(self, scope):
        assert scope == SCOPE
        return result(self.contexts)

    def list_artifact_families(self, scope):
        assert scope == SCOPE
        return result(self.families)

    def list_media_gate_sets(self, scope):
        assert scope == SCOPE
        return result(self.gates)

    def list_review_issues(self, scope):
        assert scope == SCOPE
        return result(self.issues)

    def list_return_decisions(self, scope):
        assert scope == SCOPE
        return result(self.returns)


def reader(*, production=None, starts=(), jobs=(), finances=(), proposals=()):
    return EcommerceWorkshopMediaStudioSourceReader(
        production_store=production or ProductionStore(),
        production_start_service=SimpleNamespace(list=lambda scope: result(list(starts))),
        provider_job_store=SimpleNamespace(list_jobs=lambda scope, limit: result(list(jobs))),
        media_finance_store=SimpleNamespace(list=lambda scope, limit: result(list(finances))),
        action_store=SimpleNamespace(list_proposals=lambda scope, limit: list(proposals)),
    )


@pytest.mark.parametrize("method", ["read_context", "read_execution", "read_delivery"])
def test_authoritative_empty_collections_are_ready_not_applicable(method: str) -> None:
    observation = getattr(reader(), method)(SCOPE, cutoff=CUTOFF, limit=100)

    assert observation.scope == SCOPE
    assert observation.data_cutoff == CUTOFF
    assert [item.axis for item in observation.readiness_axes] == list(MediaReadinessAxis)
    assert all(item.status == "not_applicable" for item in observation.readiness_axes)
    assert observation.authority_refs == ()


def test_non_empty_authority_without_exact_receipt_fails_closed() -> None:
    instance = reader(production=ProductionStore(contexts=[SimpleNamespace(created_at=CUTOFF)]))

    with pytest.raises(MediaStudioReadError, match="exact Receipt"):
        instance.read_context(SCOPE, cutoff=CUTOFF, limit=100)


def test_future_execution_authority_does_not_cross_the_cutoff() -> None:
    future = datetime(2026, 9, 6, tzinfo=UTC)
    observation = reader(
        jobs=[SimpleNamespace(created_at=future)],
        finances=[SimpleNamespace(created_at=future)],
    ).read_execution(SCOPE, cutoff=CUTOFF, limit=100)

    assert all(item.status == "not_applicable" for item in observation.readiness_axes)


def test_reader_requires_timezone_and_canonical_limit() -> None:
    instance = reader()

    with pytest.raises(MediaStudioReadError, match="timezone"):
        instance.read_context(SCOPE, cutoff=datetime(2026, 9, 5), limit=100)
    with pytest.raises(MediaStudioReadError, match="limit"):
        instance.read_context(SCOPE, cutoff=CUTOFF, limit=101)


def test_one_dependency_error_fails_only_the_requested_slice() -> None:
    broken = ProductionStore()
    broken.list_artifact_families = lambda scope: (_ for _ in ()).throw(RuntimeError("db down"))

    with pytest.raises(MediaStudioReadError, match="delivery"):
        reader(production=broken).read_delivery(SCOPE, cutoff=CUTOFF, limit=100)
