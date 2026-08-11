from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aos_api.aip_contracts import TenantContext
from aos_api.aip_eval_authority_store import AipEvalAuthorityNotFound
from aos_api.aip_eval_contracts import (
    EvidenceQuality,
    SpanKind,
    SpanStatus,
    TelemetrySpan,
    UsageAdjustment,
    UsageKind,
    UsageReceipt,
)
from aos_api.auth import Principal, require_principal
from aos_api.routers.aip_telemetry_usage import (
    get_aip_telemetry_usage_service,
    router,
)
from aos_api.tenant_scope import TenantScope

HASH = "a" * 64
NOW = datetime(2026, 8, 11, tzinfo=UTC)


@pytest.fixture()
def telemetry_api(client):
    client.app.include_router(router)
    span = TelemetrySpan(
        tenant=TenantContext(org_id="dev-org", project_id="dev-project"),
        span_record_id="span-record-1",
        provider="otel",
        provider_receipt_id="provider-span-1",
        lineage_id="lineage-1",
        trace_id="trace-1",
        span_id="span-1",
        name="model.call",
        kind=SpanKind.MODEL,
        status=SpanStatus.OK,
        producer_started_at=NOW,
        observed_at=NOW,
        ingested_at=NOW,
        attributes_hash=HASH,
        source_hash=HASH,
        quality=EvidenceQuality.MEASURED,
    )
    usage = UsageReceipt(
        tenant=TenantContext(org_id="dev-org", project_id="dev-project"),
        receipt_id="usage-record-1",
        provider="model-provider",
        provider_receipt_id="provider-usage-1",
        lineage_id="lineage-1",
        usage_kind=UsageKind.INPUT_TOKEN,
        quantity=123,
        unit="token",
        quality=EvidenceQuality.MEASURED,
        source_hash=HASH,
        observed_at=NOW,
    )
    adjustment = UsageAdjustment(
        tenant=TenantContext(org_id="dev-org", project_id="dev-project"),
        adjustment_id="adjustment-1",
        receipt_id="usage-record-1",
        delta=-3,
        reason_hash=HASH,
        actor="dev-user",
        created_at=NOW,
    )

    class FakeService:
        def __init__(self) -> None:
            self.calls: list[tuple[str, TenantScope]] = []
            self.error: Exception | None = None

        def _result(self, kind, scope):
            self.calls.append((kind, scope))
            if self.error:
                raise self.error
            return span

        def ingest_span(self, scope, request, *, ingested_at=None):
            return self._result("ingest", scope)

        def list_spans(self, scope, lineage_id):
            return [self._result("list", scope)]

        def ingest_usage(self, scope, request):
            self.calls.append(("ingest-usage", scope))
            return usage

        def list_usage(self, scope, lineage_id):
            self.calls.append(("list-usage", scope))
            return [usage]

        def append_adjustment(self, scope, request, *, actor):
            self.calls.append((f"adjust:{actor}", scope))
            return adjustment

        def list_adjustments(self, scope, receipt_id):
            self.calls.append(("list-adjustments", scope))
            return [adjustment]

    service = FakeService()
    client.app.dependency_overrides[get_aip_telemetry_usage_service] = lambda: service
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }
    yield client, service, headers
    client.app.dependency_overrides.pop(get_aip_telemetry_usage_service, None)


def test_span_api_uses_authenticated_scope_and_runtime_role(telemetry_api) -> None:
    client, service, headers = telemetry_api
    body = {
        "provider": "otel",
        "providerReceiptId": "provider-span-1",
        "lineageId": "lineage-1",
        "traceId": "trace-1",
        "spanId": "span-1",
        "name": "model.call",
        "kind": "model",
        "status": "ok",
        "producerStartedAt": NOW.isoformat(),
        "observedAt": NOW.isoformat(),
        "attributesHash": HASH,
        "sourceHash": HASH,
        "quality": "measured",
    }
    response = client.post(
        "/v1/aip/telemetry-authority/spans", headers=headers, json=body
    )
    assert response.status_code == 200
    listed = client.get(
        "/v1/aip/telemetry-authority/lineages/lineage-1/spans", headers=headers
    )
    assert listed.status_code == 200
    assert service.calls == [
        ("ingest", TenantScope("dev-org", "dev-project")),
        ("list", TenantScope("dev-org", "dev-project")),
    ]


def test_telemetry_api_fails_closed(telemetry_api) -> None:
    client, service, headers = telemetry_api
    service.error = AipEvalAuthorityNotFound("missing")
    response = client.get(
        "/v1/aip/telemetry-authority/lineages/missing/spans", headers=headers
    )
    assert response.status_code == 404
    assert response.json()["code"] == "AIP_EVAL_AUTHORITY_NOT_FOUND"


def test_telemetry_api_requires_authentication(telemetry_api) -> None:
    client, _service, _headers = telemetry_api
    response = client.get("/v1/aip/telemetry-authority/lineages/lineage-1/spans")
    assert response.status_code in {401, 403}


def test_usage_and_adjustment_api_use_authenticated_scope(telemetry_api) -> None:
    client, service, headers = telemetry_api
    usage_body = {
        "provider": "model-provider",
        "providerReceiptId": "provider-usage-1",
        "lineageId": "lineage-1",
        "usageKind": "input_token",
        "quantity": 123,
        "unit": "token",
        "quality": "measured",
        "sourceHash": HASH,
        "observedAt": NOW.isoformat(),
    }
    response = client.post(
        "/v1/aip/telemetry-authority/usage-receipts",
        headers=headers,
        json=usage_body,
    )
    assert response.status_code == 200
    assert (
        client.get(
            "/v1/aip/telemetry-authority/lineages/lineage-1/usage-receipts",
            headers=headers,
        ).status_code
        == 200
    )
    adjustment_body = {
        "adjustmentId": "adjustment-1",
        "receiptId": "usage-record-1",
        "delta": -3,
        "reasonHash": HASH,
    }
    assert (
        client.post(
            "/v1/aip/telemetry-authority/usage-adjustments",
            headers=headers,
            json=adjustment_body,
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/v1/aip/telemetry-authority/usage-receipts/usage-record-1/adjustments",
            headers=headers,
        ).status_code
        == 200
    )
    scope = TenantScope("dev-org", "dev-project")
    assert service.calls == [
        ("ingest-usage", scope),
        ("list-usage", scope),
        ("adjust:user:dev", scope),
        ("list-adjustments", scope),
    ]


def test_telemetry_writes_require_runtime_role(telemetry_api) -> None:
    client, service, headers = telemetry_api
    client.app.dependency_overrides[require_principal] = lambda: Principal(
        subject="readonly-user",
        org_id="dev-org",
        project_id="dev-project",
        roles=["viewer"],
        markings=["public"],
    )
    try:
        response = client.post(
            "/v1/aip/telemetry-authority/usage-receipts",
            headers=headers,
            json={
                "provider": "model-provider",
                "providerReceiptId": "provider-usage-1",
                "lineageId": "lineage-1",
                "usageKind": "input_token",
                "quantity": 123,
                "unit": "token",
                "quality": "measured",
                "sourceHash": HASH,
                "observedAt": NOW.isoformat(),
            },
        )
    finally:
        client.app.dependency_overrides.pop(require_principal, None)
    assert response.status_code == 403
    assert service.calls == []
