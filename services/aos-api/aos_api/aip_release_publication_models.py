"""Canonical AIP-4 E2 request/response contracts for release and publication."""
from __future__ import annotations

from pydantic import Field

from aos_api.aip_contracts import AipContractModel
from aos_api.aip_eval_contracts import PublicationEvent, ReleaseGateDecision


class DeriveReleaseGateRequest(AipContractModel):
    report_id: str = Field(min_length=1, max_length=200)
    report_revision: int = Field(ge=1)
    report_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=1, max_length=200)


class PublishReleaseRequest(AipContractModel):
    release_gate_decision_id: str = Field(min_length=1, max_length=200)
    reason_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=1, max_length=200)


class RevokePublicationRequest(AipContractModel):
    reason_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=1, max_length=200)


class ReleasePublicationResponse(AipContractModel):
    gate: ReleaseGateDecision
    event: PublicationEvent


__all__ = [
    "DeriveReleaseGateRequest",
    "PublishReleaseRequest",
    "ReleasePublicationResponse",
    "RevokePublicationRequest",
]
