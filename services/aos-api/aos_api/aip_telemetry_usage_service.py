"""Canonical orchestration for persistent AIP telemetry and usage facts."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from aos_api.aip_contracts import TenantContext
from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
from aos_api.aip_eval_contracts import (
    TelemetrySpan,
    TelemetrySpanIngestRequest,
    UsageAdjustment,
    UsageAdjustmentRequest,
    UsageReceipt,
    UsageReceiptIngestRequest,
)
from aos_api.tenant_scope import TenantScope


class AipTelemetryUsageService:
    """Assign server identities and delegate all persistence to the authority store."""

    def __init__(self, store: AipEvalAuthorityStore | None = None) -> None:
        self._store = store or AipEvalAuthorityStore()

    def ingest_span(
        self,
        scope: TenantScope,
        request: TelemetrySpanIngestRequest,
        *,
        ingested_at: datetime | None = None,
    ) -> TelemetrySpan:
        span = TelemetrySpan(
            tenant=self._tenant(scope),
            span_record_id=self._authority_id(
                "span", scope, request.provider, request.provider_receipt_id
            ),
            ingested_at=ingested_at or datetime.now(UTC),
            **request.model_dump(),
        )
        return self._store.append_telemetry_span(scope, span)

    def ingest_usage(
        self,
        scope: TenantScope,
        request: UsageReceiptIngestRequest,
    ) -> UsageReceipt:
        receipt = UsageReceipt(
            tenant=self._tenant(scope),
            receipt_id=self._authority_id(
                "usage", scope, request.provider, request.provider_receipt_id
            ),
            **request.model_dump(),
        )
        return self._store.append_usage_receipt(scope, receipt)

    def append_adjustment(
        self,
        scope: TenantScope,
        request: UsageAdjustmentRequest,
        *,
        actor: str,
        created_at: datetime | None = None,
    ) -> UsageAdjustment:
        adjustment = UsageAdjustment(
            tenant=self._tenant(scope),
            actor=actor,
            created_at=created_at or datetime.now(UTC),
            **request.model_dump(),
        )
        return self._store.append_usage_adjustment(scope, adjustment)

    def list_spans(self, scope: TenantScope, lineage_id: str) -> list[TelemetrySpan]:
        return self._store.list_telemetry_spans(scope, lineage_id)

    def list_usage(self, scope: TenantScope, lineage_id: str) -> list[UsageReceipt]:
        return self._store.list_usage_receipts(scope, lineage_id)

    def list_adjustments(
        self, scope: TenantScope, receipt_id: str
    ) -> list[UsageAdjustment]:
        return self._store.list_usage_adjustments(scope, receipt_id)

    @staticmethod
    def _authority_id(
        prefix: str,
        scope: TenantScope,
        provider: str,
        provider_receipt_id: str,
    ) -> str:
        digest = hashlib.sha256(
            f"{scope.org_id}:{scope.project_id}:{provider}:{provider_receipt_id}".encode()
        ).hexdigest()[:28]
        return f"{prefix}-{digest}"

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)


__all__ = ["AipTelemetryUsageService"]
