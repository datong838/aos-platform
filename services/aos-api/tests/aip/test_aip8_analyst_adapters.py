from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_analyst_contracts import (
    AnalystQueryStatus,
    QueryColumn,
    QueryRow,
    QuerySourceRef,
    SemanticQueryRequest,
)
from aos_api.aip_analyst_query import (
    AdapterResult,
    AnalystReadAdapters,
    CanonicalAdapterBlocked,
    execute_analyst_query,
)
from aos_api.aip_contracts import ResourceRef
from aos_api.auth import Principal
from aos_api.tenant_scope import TenantScope


NOW = datetime.now(UTC)
SCOPE = TenantScope("org-org", "dev-project")
PRINCIPAL = Principal(
    subject="developer",
    org_id=SCOPE.org_id,
    project_id=SCOPE.project_id,
    roles=["developer"],
    markings=["public"],
)


class SemanticAdapter:
    def __init__(self) -> None:
        self.seen_scope: tuple[str, str] | None = None

    def execute(self, scope, principal, request):
        self.seen_scope = scope.key
        assert principal.subject == "developer"
        assert request.object_type == "Order"
        return AdapterResult(
            status=AnalystQueryStatus.COMPLETE,
            columns=[QueryColumn(key="orderNo", label="订单", value_type="string")],
            rows=[QueryRow(row_id="order-1", values={"orderNo": "20260815001"})],
            source_refs=[
                QuerySourceRef(
                    ref=ResourceRef(
                        resource_type="ObjectTypeRevision",
                        resource_id="Order",
                        revision="12",
                        authority="ontology",
                    ),
                    content_hash="b" * 64,
                    cutoff_at=NOW,
                    freshness="fresh",
                    markings=["public"],
                )
            ],
            lineage_refs=[],
            uncertainties=[],
        )


def test_missing_adapter_returns_tenant_scoped_blocked_result() -> None:
    request = SemanticQueryRequest(object_type="Order", cutoff_at=NOW)
    result = execute_analyst_query(
        scope=SCOPE,
        principal=PRINCIPAL,
        request=request,
        adapters=AnalystReadAdapters(),
    )
    assert result.status == AnalystQueryStatus.BLOCKED
    assert result.tenant.org_id == "org-org"
    assert result.rows == []
    assert result.blockers[0].code == "SEMANTIC_ADAPTER_UNAVAILABLE"


def test_semantic_adapter_receives_server_scope_and_exact_sources() -> None:
    adapter = SemanticAdapter()
    request = SemanticQueryRequest(object_type="Order", cutoff_at=NOW)
    result = execute_analyst_query(
        scope=SCOPE,
        principal=PRINCIPAL,
        request=request,
        adapters=AnalystReadAdapters(semantic=adapter),
    )
    assert adapter.seen_scope == SCOPE.key
    assert result.status == AnalystQueryStatus.COMPLETE
    assert result.rows[0].values["orderNo"] == "20260815001"
    assert result.source_refs[0].ref.revision == "12"
    assert len(result.content_hash) == 64


def test_cross_scope_principal_is_rejected_before_adapter() -> None:
    request = SemanticQueryRequest(object_type="Order", cutoff_at=NOW)
    with pytest.raises(ValueError, match="scope"):
        execute_analyst_query(
            scope=TenantScope("dev-org", "dev-project"),
            principal=PRINCIPAL,
            request=request,
            adapters=AnalystReadAdapters(semantic=SemanticAdapter()),
        )


def test_canonical_adapter_blocker_becomes_typed_blocked_result() -> None:
    class BlockedAdapter:
        def execute(self, scope, principal, request):
            raise CanonicalAdapterBlocked(
                code="OBJECT_FIELD_UNAVAILABLE",
                message="requested field is not in the installed schema",
                retryable=False,
            )

    result = execute_analyst_query(
        scope=SCOPE,
        principal=PRINCIPAL,
        request=SemanticQueryRequest(object_type="Order", cutoff_at=NOW),
        adapters=AnalystReadAdapters(semantic=BlockedAdapter()),
    )
    assert result.status == AnalystQueryStatus.BLOCKED
    assert result.blockers[0].code == "OBJECT_FIELD_UNAVAILABLE"
    assert result.blockers[0].retryable is False


def test_future_cutoff_is_typed_blocked_before_adapter() -> None:
    result = execute_analyst_query(
        scope=SCOPE,
        principal=PRINCIPAL,
        request=SemanticQueryRequest(
            object_type="Order",
            cutoff_at=datetime.now(UTC) + timedelta(minutes=1),
        ),
        adapters=AnalystReadAdapters(semantic=SemanticAdapter()),
    )
    assert result.status == AnalystQueryStatus.BLOCKED
    assert result.blockers[0].code == "QUERY_CUTOFF_IN_FUTURE"
