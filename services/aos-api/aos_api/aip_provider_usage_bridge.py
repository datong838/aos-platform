"""Bridge provider usage envelopes into the existing AIP-4 usage authority."""
from __future__ import annotations

from typing import Any

from aos_api.aip_eval_contracts import UsageReceiptIngestRequest
from aos_api.aip_model_runtime_contracts import ModelRouteResolution
from aos_api.aip_telemetry_usage_service import AipTelemetryUsageService
from aos_api.tenant_scope import TenantScope


class AipProviderUsageEnvelopeError(RuntimeError):
    pass


class AipProviderUsageBridge:
    def __init__(self, service: AipTelemetryUsageService | None = None) -> None:
        self._service = service or AipTelemetryUsageService()

    def record(
        self,
        scope: TenantScope,
        lineage_id: str,
        resolution: ModelRouteResolution,
        response: dict[str, Any],
    ) -> list[str]:
        if resolution.selected_provider is None:
            raise AipProviderUsageEnvelopeError("exact_provider_ref_required")
        provider_receipt_id = response.get("providerReceiptId")
        receipts = response.get("usageReceipts")
        if not isinstance(provider_receipt_id, str) or not provider_receipt_id.strip():
            raise AipProviderUsageEnvelopeError("provider_receipt_id_required")
        if not isinstance(receipts, list) or not receipts:
            raise AipProviderUsageEnvelopeError("provider_usage_receipts_required")
        provider = resolution.selected_provider.asset_id
        stored: list[str] = []
        for index, raw in enumerate(receipts):
            if not isinstance(raw, dict):
                raise AipProviderUsageEnvelopeError("provider_usage_receipt_invalid")
            request = UsageReceiptIngestRequest(
                provider=provider,
                providerReceiptId=f"{provider_receipt_id}:{index}:{raw.get('usageKind', 'unknown')}",
                lineageId=lineage_id,
                **raw,
            )
            stored.append(self._service.ingest_usage(scope, request).receipt_id)
        return stored


__all__ = ["AipProviderUsageBridge", "AipProviderUsageEnvelopeError"]
