"""Exact AIP Action adapter contract for one text Provider Health cycle.

Importing this module does not register the adapter or authorize execution.
The canonical AIP Action chain must own Proposal, Approval, ExecutionLease,
Attempt and Receipt before an instance may be invoked.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Literal

from pydantic import Field

from aos_api.aip_action_adapters import AdapterOutcome
from aos_api.aip_contracts import AipContractModel

PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID = "aip.provider-health-probe"
TEXT_PROVIDER_ID = "agnes-text-qyh-dev"
TEXT_PROVIDER_REVISION = 7
TEXT_PROVIDER_PROBE_COUNT = 3


class ProviderHealthActionBlocked(RuntimeError):
    """Stable adapter failure that contains no Provider or Secret payload."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ProviderHealthProbePayload(AipContractModel):
    provider_id: Literal["agnes-text-qyh-dev"]
    provider_revision: Literal[7]
    probe_count: Literal[3]
    output_policy: Literal["metadata-only"] = "metadata-only"


class ProviderHealthProbeReceipt(AipContractModel):
    observation_id: str = Field(min_length=1, max_length=240)
    expires_at: datetime
    provider_calls: Literal[3]
    secret_payload_reads_reported: Literal[0] = 0
    prompt_or_answer_bodies_reported: Literal[0] = 0


class ProviderHealthProbeActionAdapter:
    """Single-attempt adapter; retry and reconciliation stay fail closed."""

    def __init__(self, refresh: Callable[[], dict[str, Any]]) -> None:
        self._refresh = refresh

    def execute(
        self, *, payload: dict[str, Any], idempotency_key: str
    ) -> AdapterOutcome:
        ProviderHealthProbePayload.model_validate(payload)
        if not idempotency_key.strip():
            raise ProviderHealthActionBlocked("ACTION_IDEMPOTENCY_REQUIRED")
        result = self._refresh()
        if result.get("status") != "PROVIDER_HEALTH_REFRESH_GREEN":
            raise ProviderHealthActionBlocked("PROVIDER_HEALTH_REFRESH_NOT_GREEN")
        try:
            receipt = ProviderHealthProbeReceipt.model_validate(
                {
                    "observationId": result.get("observationId"),
                    "expiresAt": result.get("expiresAt"),
                    "providerCalls": result.get("providerCalls"),
                    "secretPayloadReadsReported": result.get(
                        "secretPayloadReadsReported"
                    ),
                    "promptOrAnswerBodiesReported": result.get(
                        "promptOrAnswerBodiesReported"
                    ),
                }
            )
        except Exception as exc:
            raise ProviderHealthActionBlocked(
                "PROVIDER_HEALTH_RECEIPT_INVALID"
            ) from exc
        return AdapterOutcome(
            status="applied",
            payload=receipt.model_dump(mode="json", by_alias=True),
        )

    def reconcile(
        self, *, provider_request_id: str, request_fingerprint: str
    ) -> AdapterOutcome:
        del provider_request_id, request_fingerprint
        return AdapterOutcome(
            status="unknown",
            payload={
                "errorType": "PROVIDER_HEALTH_RECONCILIATION_UNAVAILABLE",
                "automaticRetry": False,
            },
        )

