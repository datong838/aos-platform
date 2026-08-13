from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.aip_memory_readiness import (
    AipMemoryReadinessError,
    AipMemoryReadinessService,
    KnowledgeAuthorityAvailability,
    KnowledgeSearchReadiness,
)
from aos_api.aip_memory_search_index import (
    SearchCapability,
    SearchCapabilityStatus,
    SearchLane,
)
from aos_api.tenant_scope import TenantScope


class Result:
    def __init__(self, rows): self.rows = rows
    def fetchone(self): return self.rows[0]
    def fetchall(self): return self.rows


class Conn:
    def execute(self, sql, _params):
        if "aip_memory_search_reference" in sql:
            return Result([{"count": 0}])
        if "aip_memory_source_revision" in sql:
            return Result([])
        if "aip_memory_search_capability" in sql:
            return Result([])
        raise AssertionError(sql)


@contextmanager
def connect(_scope):
    yield Conn()


def test_readiness_is_tenant_scoped_and_honestly_blocked() -> None:
    view = AipMemoryReadinessService(connect).read(
        TenantScope("org-org", "dev-project"),
        search_provider_configured=False,
        observed_at=datetime(2026, 8, 13, tzinfo=UTC),
    )
    assert view.tenant.org_id == "org-org"
    assert view.package.status == "authority_unavailable"
    assert view.package.count is None
    assert view.sources == []
    assert view.source_blockers == ["knowledge_source_missing"]
    assert view.search.reference_count == 0
    assert [item.lane.value for item in view.search.capabilities] == ["fulltext", "vector", "rerank"]
    assert "trusted_search_provider_unavailable" in view.search.blockers
    assert view.eval.count is None
    payload = view.model_dump(by_alias=True, mode="json")
    assert payload["search"]["capabilities"][0]["reasonCode"] == "capability_not_registered"
    assert "reason_code" not in payload["search"]["capabilities"][0]


def test_authority_state_rejects_contradictory_count_and_blocker() -> None:
    with pytest.raises(ValidationError):
        KnowledgeAuthorityAvailability(
            status="authority_unavailable", count=1, blocker="missing"
        )


def test_search_readiness_requires_each_lane_exactly_once() -> None:
    now = datetime(2026, 8, 13, tzinfo=UTC)
    duplicate = SearchCapability(
        lane=SearchLane.FULLTEXT,
        status=SearchCapabilityStatus.UNBUILT,
        reason_code="missing",
        version=1,
        observed_at=now,
    )
    with pytest.raises(ValidationError):
        KnowledgeSearchReadiness(
            reference_count=0,
            provider_configured=False,
            capabilities=[duplicate, duplicate, duplicate],
            blockers=["missing"],
        )


@contextmanager
def broken_connect(_scope):
    raise RuntimeError("database unavailable")
    yield


def test_readiness_wraps_storage_failures() -> None:
    with pytest.raises(AipMemoryReadinessError):
        AipMemoryReadinessService(broken_connect).read(
            TenantScope("org-org", "dev-project"),
            search_provider_configured=False,
        )
