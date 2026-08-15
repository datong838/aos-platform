from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.aip_analyst_contracts import (
    ANALYST_QUERY_ADAPTER,
    AnalystQueryStatus,
    MetricQueryRequest,
    QueryBlocker,
    QueryResultRevision,
)
from aos_api.aip_contracts import ResourceRef, TenantContext


NOW = datetime.now(UTC)
HASH = "a" * 64


def test_discriminated_request_rejects_tenant_and_sql() -> None:
    with pytest.raises(ValidationError):
        ANALYST_QUERY_ADAPTER.validate_python(
            {
                "kind": "semantic",
                "objectType": "Order",
                "cutoffAt": NOW,
                "orgId": "dev-org",
                "sql": "SELECT * FROM orders",
            }
        )


def test_metric_window_must_end_by_cutoff() -> None:
    ref = ResourceRef(
        resource_type="MetricDefinitionRevision",
        resource_id="gmv",
        revision="1",
        authority="aip-eval",
    )
    with pytest.raises(ValidationError):
        MetricQueryRequest(
            metric_ref=ref,
            window_start=NOW - timedelta(days=1),
            window_end=NOW + timedelta(minutes=1),
            cutoff_at=NOW,
        )


def test_blocked_result_cannot_contain_rows_or_sources() -> None:
    with pytest.raises(ValidationError):
        QueryResultRevision(
            tenant=TenantContext(org_id="org-org", project_id="dev-project"),
            query_id="qry-1",
            revision=1,
            kind="semantic",
            status=AnalystQueryStatus.BLOCKED,
            columns=[],
            rows=[{"rowId": "1", "values": {"x": 1}}],
            source_refs=[],
            blockers=[QueryBlocker(code="NO_ADAPTER", message="missing")],
            cutoff_at=NOW,
            content_hash=HASH,
            created_at=NOW,
        )


def test_blocked_result_requires_machine_reason() -> None:
    with pytest.raises(ValidationError):
        QueryResultRevision(
            tenant=TenantContext(org_id="org-org", project_id="dev-project"),
            query_id="qry-1",
            revision=1,
            kind="knowledge",
            status="blocked",
            cutoff_at=NOW,
            content_hash=HASH,
            created_at=NOW,
        )


def test_result_rows_must_match_columns_and_source_cutoff() -> None:
    source = {
        "ref": {
            "resourceType": "ObjectTypeRevision",
            "resourceId": "Order",
            "revision": "12",
            "authority": "ontology",
        },
        "contentHash": HASH,
        "cutoffAt": NOW + timedelta(minutes=1),
        "freshness": "fresh",
        "markings": ["public"],
    }
    with pytest.raises(ValidationError):
        QueryResultRevision(
            tenant=TenantContext(org_id="org-org", project_id="dev-project"),
            query_id="qry-1",
            revision=1,
            kind="semantic",
            status="complete",
            columns=[{"key": "orderNo", "label": "订单", "valueType": "string"}],
            rows=[{"rowId": "1", "values": {"undeclared": "x"}}],
            source_refs=[source],
            cutoff_at=NOW,
            content_hash=HASH,
            created_at=NOW,
        )
