from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from aos_api.aip_analyst_canonical_adapters import (
    CanonicalKnowledgeReadAdapter,
    CanonicalSemanticReadAdapter,
)
from aos_api.aip_analyst_contracts import (
    AnalystQueryStatus,
    KnowledgeQueryRequest,
    MetricQueryRequest,
    QueryFilter,
    QuerySort,
    SemanticQueryRequest,
)
from aos_api.aip_analyst_query import AnalystReadAdapters, execute_analyst_query
from aos_api.aip_contracts import ResourceRef
from aos_api.auth import Principal
from aos_api.ontology_object_redaction import redact_ecommerce_pii
from aos_api.routers.aip_analyst import get_aip_analyst_read_adapters
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
PRINCIPAL = Principal(
    subject="developer",
    org_id=SCOPE.org_id,
    project_id=SCOPE.project_id,
    roles=["developer"],
    markings=["public"],
)
NOW = datetime.now(UTC)


class FakeConn:
    def __init__(self) -> None:
        self.scope_seen: tuple[str, str] | None = None

    def execute(self, sql, params=()):
        normalized = " ".join(str(sql).split())
        if "FROM meta_object_type" in normalized:
            return SimpleNamespace(
                fetchone=lambda: {
                    "id": "Order",
                    "name": "订单",
                    "properties": [
                        {"name": "orderNo", "type": "string"},
                        {"name": "totalAmount", "type": "number"},
                        {"name": "createdAt", "type": "datetime"},
                    ],
                }
            )
        if "FROM ecom_object" in normalized:
            assert params[:3] == (*SCOPE.key, "Order")
            return SimpleNamespace(
                fetchall=lambda: [
                    {
                        "external_id": "old",
                        "properties": {
                            "orderNo": "OLD",
                            "totalAmount": 20,
                            "createdAt": (NOW - timedelta(days=2)).isoformat(),
                        },
                        "source_updated_at": NOW - timedelta(days=2),
                        "payload_hash": "a" * 64,
                    },
                    {
                        "external_id": "new",
                        "properties": {
                            "orderNo": "NEW",
                            "totalAmount": 80,
                            "createdAt": (NOW - timedelta(days=1)).isoformat(),
                        },
                        "source_updated_at": NOW - timedelta(days=1),
                        "payload_hash": "b" * 64,
                    },
                    {
                        "external_id": "future",
                        "properties": {
                            "orderNo": "FUTURE",
                            "totalAmount": 100,
                            "createdAt": (NOW + timedelta(days=1)).isoformat(),
                        },
                        "source_updated_at": NOW + timedelta(days=1),
                        "payload_hash": "c" * 64,
                    },
                ]
            )
        raise AssertionError(normalized)


@contextmanager
def fake_connect(scope):
    assert scope == SCOPE
    yield FakeConn()


def _semantic_adapter() -> CanonicalSemanticReadAdapter:
    return CanonicalSemanticReadAdapter(
        connect_factory=fake_connect,
        assert_visible=lambda conn, scope, object_type: None,
        can_access=lambda principal, conn, object_type, object_id: object_id != "old",
        project=lambda principal, conn, object_type, object_id, props, schema: {
            "id": object_id,
            "type": object_type,
            **props,
        },
        markings_for=lambda conn, scope, object_type, object_id: ["public"],
    )


def test_semantic_adapter_reads_canonical_rows_with_cutoff_filter_and_sort() -> None:
    request = SemanticQueryRequest(
        object_type="Order",
        filters=[QueryFilter(field="totalAmount", operator="gte", value=50)],
        sort=[QuerySort(field="createdAt", direction="desc")],
        page_size=20,
        cutoff_at=NOW,
    )
    result = execute_analyst_query(
        scope=SCOPE,
        principal=PRINCIPAL,
        request=request,
        adapters=AnalystReadAdapters(semantic=_semantic_adapter()),
    )
    assert result.status == AnalystQueryStatus.COMPLETE
    assert [row.row_id for row in result.rows] == ["Order/new"]
    assert result.rows[0].values["orderNo"] == "NEW"
    assert result.source_refs[-1].ref.authority == "ecom_object"
    assert result.source_refs[-1].content_hash == "b" * 64
    assert all(source.cutoff_at <= NOW for source in result.source_refs)


def test_semantic_unknown_field_and_wrong_selection_fail_closed() -> None:
    unknown = execute_analyst_query(
        scope=SCOPE,
        principal=PRINCIPAL,
        request=SemanticQueryRequest(
            object_type="Order",
            filters=[QueryFilter(field="sql", operator="contains", value="SELECT")],
            cutoff_at=NOW,
        ),
        adapters=AnalystReadAdapters(semantic=_semantic_adapter()),
    )
    assert unknown.status == AnalystQueryStatus.BLOCKED
    assert unknown.blockers[0].code == "OBJECT_FIELD_UNAVAILABLE"

    wrong_selection = execute_analyst_query(
        scope=SCOPE,
        principal=PRINCIPAL,
        request=SemanticQueryRequest(
            object_type="Order",
            selection_refs=[
                ResourceRef(
                    resource_type="EcommerceObjectRevision",
                    resource_id="Product/new",
                    revision="b" * 64,
                    authority="ecom_object",
                )
            ],
            cutoff_at=NOW,
        ),
        adapters=AnalystReadAdapters(semantic=_semantic_adapter()),
    )
    assert wrong_selection.status == AnalystQueryStatus.BLOCKED
    assert wrong_selection.blockers[0].code == "SELECTION_REFERENCE_INVALID"

    drifted_selection = execute_analyst_query(
        scope=SCOPE,
        principal=PRINCIPAL,
        request=SemanticQueryRequest(
            object_type="Order",
            selection_refs=[
                ResourceRef(
                    resource_type="EcommerceObjectRevision",
                    resource_id="Order/new",
                    revision="f" * 64,
                    authority="ecom_object",
                )
            ],
            cutoff_at=NOW,
        ),
        adapters=AnalystReadAdapters(semantic=_semantic_adapter()),
    )
    assert drifted_selection.status == AnalystQueryStatus.BLOCKED
    assert drifted_selection.blockers[0].code == "SELECTION_REFERENCE_DRIFT"


def test_semantic_numeric_sort_uses_schema_type_instead_of_lexical_order() -> None:
    request = SemanticQueryRequest(
        object_type="Order",
        sort=[QuerySort(field="totalAmount", direction="desc")],
        page_size=20,
        cutoff_at=NOW + timedelta(days=2),
    )
    result = _semantic_adapter().execute(SCOPE, PRINCIPAL, request)
    assert [row.row_id for row in result.rows] == ["Order/future", "Order/new"]


class FakeKnowledgeSearch:
    def __init__(self, *, blocked: bool = False) -> None:
        self.blocked = blocked
        self.seen = None

    def search(self, scope, request, *, authorized_markings, required_applicability):
        self.seen = (scope, request, authorized_markings, required_applicability)
        if self.blocked:
            return SimpleNamespace(
                status="blocked",
                blocked_reasons=["fulltext_index_unbuilt"],
                matches=[],
            )
        citation = SimpleNamespace(
            memory_item_id="mem-1",
            revision=4,
            content_hash="d" * 64,
            source=SimpleNamespace(observed_at=NOW - timedelta(days=1)),
            freshness="active",
            markings=["public"],
        )
        return SimpleNamespace(
            status="complete",
            blocked_reasons=[],
            matches=[
                SimpleNamespace(
                    citation=citation,
                    chunk=SimpleNamespace(content="退款审核需要人工确认", token_count=12),
                    score=0.9,
                )
            ],
        )


def _knowledge_request() -> KnowledgeQueryRequest:
    return KnowledgeQueryRequest(
        query="退款审核",
        task_ref=ResourceRef(
            resource_type="TaskRevision",
            resource_id="task-1",
            revision="3",
            authority="aip-task",
        ),
        skill_ref=ResourceRef(
            resource_type="SkillRevision",
            resource_id="customer-service",
            revision="2",
            authority="aip-registry",
        ),
        markings=["public"],
        cutoff_at=NOW,
    )


def test_knowledge_adapter_preserves_exact_citation_and_blockers() -> None:
    service = FakeKnowledgeSearch()
    complete = execute_analyst_query(
        scope=SCOPE,
        principal=PRINCIPAL,
        request=_knowledge_request(),
        adapters=AnalystReadAdapters(
            knowledge=CanonicalKnowledgeReadAdapter(service)
        ),
    )
    assert complete.status == AnalystQueryStatus.COMPLETE
    assert complete.rows[0].values["content"] == "退款审核需要人工确认"
    assert complete.source_refs[0].ref.resource_id == "mem-1"
    assert complete.source_refs[0].ref.revision == "4"

    blocked = execute_analyst_query(
        scope=SCOPE,
        principal=PRINCIPAL,
        request=_knowledge_request(),
        adapters=AnalystReadAdapters(
            knowledge=CanonicalKnowledgeReadAdapter(FakeKnowledgeSearch(blocked=True))
        ),
    )
    assert blocked.status == AnalystQueryStatus.BLOCKED
    assert blocked.blockers[0].code == "KNOWLEDGE_AUTHORITY_BLOCKED"
    assert "fulltext_index_unbuilt" in blocked.blockers[0].message


def test_production_adapter_factory_is_honest_about_unavailable_owners() -> None:
    adapters = get_aip_analyst_read_adapters()
    assert adapters.semantic is not None
    assert adapters.knowledge is None
    assert adapters.metric is None


def test_metric_query_blocks_without_canonical_metric_owner() -> None:
    result = execute_analyst_query(
        scope=SCOPE,
        principal=PRINCIPAL,
        request=MetricQueryRequest(
            metric_ref=ResourceRef(
                resource_type="MetricRevision",
                resource_id="gmv",
                revision="1",
                authority="metric-catalog",
            ),
            window_start=NOW - timedelta(days=7),
            window_end=NOW - timedelta(days=1),
            cutoff_at=NOW,
        ),
        adapters=AnalystReadAdapters(),
    )
    assert result.status == AnalystQueryStatus.BLOCKED
    assert result.blockers[0].code == "METRIC_ADAPTER_UNAVAILABLE"


def test_shared_ecommerce_pii_redaction_masks_customer_identifiers() -> None:
    result = redact_ecommerce_pii(
        {"orderNo": "O-1", "mobile": "13800000000", "emailBackup": "x@y.z"}
    )
    assert result["orderNo"] == "O-1"
    assert result["mobile"] == "[REDACTED]"
    assert result["emailBackup"] == "[REDACTED]"
    assert result["_redactedFields"] == ["emailBackup", "mobile"]
