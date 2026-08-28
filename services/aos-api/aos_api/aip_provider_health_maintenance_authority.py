"""Consume one canonical Action Lease for Provider Health maintenance.

The consumer owns neither proposal creation nor approval nor lease acquisition.
It only executes a caller-supplied exact lease and accepts the resulting
metadata-only initial Receipt after strict authority checks.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aos_api.aip_action_execution import AipActionExecutionService
from aos_api.aip_provider_health_action import (
    PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
    ProviderHealthProbePayload,
    ProviderHealthProbeReceipt,
)
from aos_api.aip_provider_health_action_authority import (
    provider_health_action_type_snapshot,
    provider_health_adapter_revision,
)
from aos_api.auth import Principal


class ProviderHealthLeaseConsumerError(RuntimeError):
    """Stable fail-closed error without Provider or Secret payloads."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ProviderHealthLeaseExecution:
    principal: Principal
    lease_id: str
    expected_proposal_hash: str

    def __post_init__(self) -> None:
        if not self.lease_id.strip():
            raise ValueError("lease_id is required")
        value = self.expected_proposal_hash.strip().lower()
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("expected_proposal_hash must be a sha256 digest")
        object.__setattr__(self, "expected_proposal_hash", value)


class ProviderHealthActionLeaseConsumer:
    """Execute and validate exactly one Provider Health Action Receipt."""

    def __init__(
        self,
        service: AipActionExecutionService,
        execution: ProviderHealthLeaseExecution,
    ) -> None:
        self._service = service
        self._execution = execution

    def __call__(self, _now: datetime) -> dict[str, Any]:
        view = self._service.execute(
            self._execution.principal,
            self._execution.lease_id,
            self._execution.expected_proposal_hash,
        )
        proposal = view.proposal
        expected_action = provider_health_action_type_snapshot()
        if (
            proposal.action_type.action_type_id
            != PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID
            or proposal.action_type.revision_hash != expected_action["revisionHash"]
        ):
            raise ProviderHealthLeaseConsumerError(
                "PROVIDER_HEALTH_ACTION_REVISION_MISMATCH"
            )
        try:
            ProviderHealthProbePayload.model_validate(proposal.payload)
        except Exception as exc:
            raise ProviderHealthLeaseConsumerError(
                "PROVIDER_HEALTH_ACTION_PAYLOAD_INVALID"
            ) from exc
        if (
            view.lease is None
            or view.lease.id != self._execution.lease_id
            or view.lease.proposal_hash != self._execution.expected_proposal_hash
        ):
            raise ProviderHealthLeaseConsumerError(
                "PROVIDER_HEALTH_EXECUTION_LEASE_MISMATCH"
            )
        expected_adapter = provider_health_adapter_revision().exact_ref().model_dump(
            mode="json", by_alias=True
        )
        if (
            view.attempt is None
            or view.attempt.status != "applied"
            or view.attempt.adapter_revision_ref != expected_adapter
        ):
            raise ProviderHealthLeaseConsumerError(
                "PROVIDER_HEALTH_ATTEMPT_NOT_EXACT_APPLIED"
            )
        receipts = [
            receipt
            for receipt in view.receipts
            if receipt.lease_id == self._execution.lease_id
            and receipt.receipt_kind == "initial"
        ]
        if len(receipts) != 1:
            raise ProviderHealthLeaseConsumerError(
                "PROVIDER_HEALTH_INITIAL_RECEIPT_NOT_UNIQUE"
            )
        receipt = receipts[0]
        if (
            receipt.status.value != "applied"
            or receipt.provider_outcome != "applied"
            or receipt.adapter_revision_ref != expected_adapter
            or receipt.attempt_id != view.attempt.id
        ):
            raise ProviderHealthLeaseConsumerError(
                "PROVIDER_HEALTH_RECEIPT_NOT_EXACT_APPLIED"
            )
        try:
            summary = ProviderHealthProbeReceipt.model_validate(
                {
                    "observationId": receipt.payload.get("observationId"),
                    "expiresAt": receipt.payload.get("expiresAt"),
                    "providerCalls": receipt.payload.get("providerCalls"),
                    "secretPayloadReadsReported": receipt.payload.get(
                        "secretPayloadReadsReported"
                    ),
                    "promptOrAnswerBodiesReported": receipt.payload.get(
                        "promptOrAnswerBodiesReported"
                    ),
                }
            )
        except Exception as exc:
            raise ProviderHealthLeaseConsumerError(
                "PROVIDER_HEALTH_RECEIPT_SUMMARY_INVALID"
            ) from exc
        return {
            "status": "PROVIDER_HEALTH_REFRESH_GREEN",
            "observationId": summary.observation_id,
            "expiresAt": summary.expires_at.isoformat(),
            "providerCalls": summary.provider_calls,
            "secretPayloadReadsReported": summary.secret_payload_reads_reported,
            "promptOrAnswerBodiesReported": (
                summary.prompt_or_answer_bodies_reported
            ),
            "actionProposalId": proposal.id,
            "actionLeaseId": view.lease.id,
            "actionAttemptId": view.attempt.id,
            "actionReceiptId": receipt.id,
            "adapterRevisionRef": expected_adapter,
        }


__all__ = [
    "ProviderHealthActionLeaseConsumer",
    "ProviderHealthLeaseConsumerError",
    "ProviderHealthLeaseExecution",
]
