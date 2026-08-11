from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_eval_authority_store import (
    AipEvalAuthorityConflict,
    AipEvalAuthorityNotFound,
)
from aos_api.aip_eval_contracts import (
    EvidenceQuality,
    SpanKind,
    SpanStatus,
    TelemetrySpanIngestRequest,
    UsageAdjustmentRequest,
    UsageKind,
    UsageReceiptIngestRequest,
)
from aos_api.aip_telemetry_usage_service import AipTelemetryUsageService
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("dev-org", "dev-project")
OTHER = TenantScope("org-org", "dev-project")
HASH = "a" * 64
H2 = "b" * 64
NOW = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)


@pytest.fixture()
def lineage_id() -> str:
    suffix = uuid.uuid4().hex[:12]
    lineage_id = f"lineage-{suffix}"
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO aip_lineage_event (
                 org_id,project_id,event_id,lineage_id,root_type,root_id,sequence,
                 event_type,payload_hash,quality,occurred_at,observed_at,
                 source_kind,source_id,source_hash
               ) VALUES (%s,%s,%s,%s,'task_run',%s,1,'input',%s,'measured',
                 %s,%s,'task_run',%s,%s)""",
            (
                *SCOPE.key,
                f"event-{suffix}",
                lineage_id,
                f"run-{suffix}",
                HASH,
                NOW,
                NOW,
                f"run-{suffix}:v1",
                HASH,
            ),
        )
        conn.commit()
    return lineage_id


def test_span_is_persistent_idempotent_and_preserves_clock_skew(lineage_id) -> None:
    service = AipTelemetryUsageService()
    request = TelemetrySpanIngestRequest(
        provider="otel-collector",
        provider_receipt_id=f"span-receipt-{uuid.uuid4().hex}",
        lineage_id=lineage_id,
        trace_id="trace-1",
        span_id="span-1",
        name="model.call",
        kind=SpanKind.MODEL,
        status=SpanStatus.OK,
        producer_started_at=NOW,
        producer_ended_at=NOW + timedelta(seconds=1),
        observed_at=NOW - timedelta(seconds=2),
        attributes_hash=HASH,
        source_hash=H2,
        quality=EvidenceQuality.MEASURED,
    )
    first = service.ingest_span(SCOPE, request, ingested_at=NOW + timedelta(seconds=3))
    assert (
        service.ingest_span(SCOPE, request, ingested_at=NOW + timedelta(seconds=9))
        == first
    )
    assert first.observed_at < first.producer_started_at
    assert service.list_spans(SCOPE, lineage_id) == [first]
    assert service.list_spans(OTHER, lineage_id) == []
    with pytest.raises(AipEvalAuthorityConflict):
        service.ingest_span(
            SCOPE,
            request.model_copy(update={"source_hash": HASH}),
            ingested_at=NOW + timedelta(seconds=4),
        )


def test_unknown_usage_has_no_quantity_and_provider_replay_is_idempotent(
    lineage_id,
) -> None:
    service = AipTelemetryUsageService()
    provider_receipt_id = f"usage-{uuid.uuid4().hex}"
    request = UsageReceiptIngestRequest(
        provider="model-provider",
        provider_receipt_id=provider_receipt_id,
        lineage_id=lineage_id,
        usage_kind=UsageKind.INPUT_TOKEN,
        quantity=None,
        unit="token",
        quality=EvidenceQuality.UNKNOWN,
        source_hash=HASH,
        observed_at=NOW,
    )
    first = service.ingest_usage(SCOPE, request)
    assert first.quantity is None
    assert service.ingest_usage(SCOPE, request) == first
    assert service.list_usage(SCOPE, lineage_id) == [first]
    with pytest.raises(AipEvalAuthorityConflict):
        service.ingest_usage(
            SCOPE,
            request.model_copy(update={"source_hash": H2}),
        )


def test_adjustment_is_append_only_and_does_not_mutate_receipt(lineage_id) -> None:
    service = AipTelemetryUsageService()
    receipt = service.ingest_usage(
        SCOPE,
        UsageReceiptIngestRequest(
            provider="model-provider",
            provider_receipt_id=f"usage-{uuid.uuid4().hex}",
            lineage_id=lineage_id,
            usage_kind=UsageKind.OUTPUT_TOKEN,
            quantity=100,
            unit="token",
            quality=EvidenceQuality.MEASURED,
            source_hash=HASH,
            observed_at=NOW,
        ),
    )
    request = UsageAdjustmentRequest(
        adjustment_id=f"adjustment-{uuid.uuid4().hex}",
        receipt_id=receipt.receipt_id,
        delta=-3,
        reason_hash=H2,
    )
    adjustment = service.append_adjustment(
        SCOPE, request, actor="tester", created_at=NOW
    )
    assert (
        service.append_adjustment(SCOPE, request, actor="tester", created_at=NOW)
        == adjustment
    )
    assert service.list_adjustments(SCOPE, receipt.receipt_id) == [adjustment]
    assert service.list_usage(SCOPE, lineage_id)[0].quantity == 100


def test_usage_and_span_require_lineage_in_same_scope() -> None:
    service = AipTelemetryUsageService()
    with pytest.raises(AipEvalAuthorityNotFound):
        service.ingest_usage(
            SCOPE,
            UsageReceiptIngestRequest(
                provider="provider",
                provider_receipt_id=f"usage-{uuid.uuid4().hex}",
                lineage_id="missing",
                usage_kind=UsageKind.COST,
                quantity=1.5,
                unit="major_currency",
                currency="USD",
                quality=EvidenceQuality.MEASURED,
                source_hash=HASH,
                observed_at=NOW,
            ),
        )
