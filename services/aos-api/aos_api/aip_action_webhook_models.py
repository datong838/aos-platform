"""Contracts for the canonical W5 Action webhook inbox."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from aos_api.aip_action_models import AipContractModel


class ActionWebhookReducerView(AipContractModel):
    attempt_id: str
    status: Literal["pending", "awaiting_gap", "applied", "failed", "partial", "disputed"]
    provider_outcome: Literal["accepted", "applied", "failed", "partial", "unknown"] | None = None
    latest_contiguous_sequence: int = Field(default=0, ge=0)
    highest_observed_sequence: int = Field(default=0, ge=0)
    missing_sequences: list[int] = Field(default_factory=list)
    observation_count: int = Field(ge=0)
    version: int = Field(ge=1)
    updated_at: datetime


class ActionWebhookObservationSnapshot(AipContractModel):
    id: str
    receipt_id: str
    attempt_id: str
    provider_event_id: str
    event_type: str
    provider_outcome: Literal["accepted", "applied", "failed", "partial", "unknown"]
    provider_sequence: int | None = Field(default=None, ge=1)
    provider_event_at: datetime | None = None
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime


class ActionWebhookInboxSnapshot(AipContractModel):
    id: str
    endpoint_revision: int = Field(ge=1)
    body_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    verification_status: Literal["verified", "rejected"]
    verification_reason: str
    replay_status: Literal["new", "duplicate", "drift", "not_checked"]
    processing_status: Literal["accepted", "quarantined", "rejected"]
    provider_event_id: str | None = None
    observation: ActionWebhookObservationSnapshot | None = None
    reducer: ActionWebhookReducerView | None = None
    case_id: str | None = None
    received_at: datetime


class WebhookEndpointSeed(AipContractModel):
    """Test/admin seed contract; never exposed by provider ingress."""

    endpoint_key: str
    endpoint_id: str
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    adapter_revision_ref: dict[str, Any]
    account_binding_ref: dict[str, Any]
    signature_policy: dict[str, Any]
    secret_ref: str
    event_schema: dict[str, Any]
    max_body_bytes: int = Field(default=65536, ge=1, le=1048576)
