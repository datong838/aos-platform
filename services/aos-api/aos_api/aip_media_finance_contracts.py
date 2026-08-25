"""W7-08 media-attempt Capacity, Budget, Usage and Settlement contracts.

The authority is append-only and currency preserving.  It never calls a
Provider, converts currencies, or treats a local cancel as zero cost.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef


class MediaFinanceEventKind(StrEnum):
    PREPARED = "prepared"
    CAPACITY_CONSUMED = "capacity_consumed"
    CAPACITY_RELEASED = "capacity_released"
    CANCEL_OBSERVED = "cancel_observed"
    USAGE_BOUND = "usage_bound"
    SETTLED = "settled"


class MediaCancelOutcome(StrEnum):
    REQUESTED = "requested"
    ACCEPTED = "accepted"
    TOO_LATE = "too_late"
    UNKNOWN = "unknown"


class MediaFeeConclusion(StrEnum):
    NO_CHARGE = "no_charge"
    CHARGEABLE = "chargeable"
    UNKNOWN = "unknown"


class MediaUsageQuality(StrEnum):
    MEASURED = "measured"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class MediaSettlementStatus(StrEnum):
    PENDING = "pending"
    SETTLED = "settled"
    DISPUTED = "disputed"
    WRITTEN_OFF = "written_off"


class PrepareMediaFinanceRequest(AipContractModel):
    job_id: str = Field(min_length=1, max_length=200)
    expected_job_sequence: int = Field(ge=1)
    capacity_pool_ref: ExactRevisionRef
    budget_revision_ref: ExactRevisionRef
    projected_min_minor: int = Field(ge=0)
    projected_max_minor: int = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    expires_at: datetime

    @model_validator(mode="after")
    def _valid(self) -> "PrepareMediaFinanceRequest":
        if self.capacity_pool_ref.resource_type != "ModelCapacityPoolRevision":
            raise ValueError("capacity_pool_ref kind drifted")
        if self.budget_revision_ref.resource_type != "BudgetRevision":
            raise ValueError("budget_revision_ref kind drifted")
        if self.projected_max_minor < self.projected_min_minor:
            raise ValueError("projected max must be at least min")
        if self.expires_at.utcoffset() is None:
            raise ValueError("finance expiry must be timezone-aware")
        return self


class ObserveMediaCancelRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    outcome: MediaCancelOutcome
    fee_conclusion: MediaFeeConclusion
    provider_receipt_ref: ExactRevisionRef | None = None
    observed_at: datetime

    @model_validator(mode="after")
    def _honest(self) -> "ObserveMediaCancelRequest":
        if self.observed_at.utcoffset() is None:
            raise ValueError("cancel observation must be timezone-aware")
        if self.fee_conclusion is MediaFeeConclusion.NO_CHARGE and self.provider_receipt_ref is None:
            raise ValueError("no-charge cancel requires Provider receipt")
        if self.provider_receipt_ref and self.provider_receipt_ref.resource_type != "MediaProviderReceipt":
            raise ValueError("cancel provider receipt kind drifted")
        return self


class TransitionMediaCapacityRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    observed_at: datetime

    @model_validator(mode="after")
    def _aware(self) -> "TransitionMediaCapacityRequest":
        if self.observed_at.utcoffset() is None:
            raise ValueError("capacity transition must be timezone-aware")
        return self


class BindMediaUsageRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    usage_receipt_ref: ExactRevisionRef
    provider_receipt_ref: ExactRevisionRef
    supersedes_usage_receipt_ref: ExactRevisionRef | None = None
    quality: MediaUsageQuality
    amount_minor: int | None = Field(default=None, ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    partial_artifact_refs: list[ExactRevisionRef] = Field(default_factory=list, max_length=32)
    observed_at: datetime

    @model_validator(mode="after")
    def _honest(self) -> "BindMediaUsageRequest":
        if self.usage_receipt_ref.resource_type != "UsageReceipt":
            raise ValueError("usage receipt kind drifted")
        if self.provider_receipt_ref.resource_type != "MediaProviderReceipt":
            raise ValueError("provider receipt kind drifted")
        if self.supersedes_usage_receipt_ref and self.supersedes_usage_receipt_ref.resource_type != "UsageReceipt":
            raise ValueError("superseded usage receipt kind drifted")
        if self.supersedes_usage_receipt_ref == self.usage_receipt_ref:
            raise ValueError("usage receipt cannot supersede itself")
        if self.quality is MediaUsageQuality.UNKNOWN and self.amount_minor is not None:
            raise ValueError("unknown usage must not invent amount")
        if self.quality is not MediaUsageQuality.UNKNOWN and self.amount_minor is None:
            raise ValueError("measured/estimated usage requires amount")
        if any(ref.resource_type != "Artifact" for ref in self.partial_artifact_refs):
            raise ValueError("partial refs must reference Artifact")
        if self.observed_at.utcoffset() is None:
            raise ValueError("usage observation must be timezone-aware")
        return self


class SettleMediaFinanceRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    status: MediaSettlementStatus
    decision_ref: ExactRevisionRef
    adjustment_minor: int = 0
    refund_minor: int = Field(default=0, ge=0)
    reason_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at: datetime

    @model_validator(mode="after")
    def _valid(self) -> "SettleMediaFinanceRequest":
        if self.status is MediaSettlementStatus.PENDING:
            raise ValueError("pending is not a settlement decision")
        if self.decision_ref.resource_type != "MediaSettlementDecision":
            raise ValueError("settlement decision kind drifted")
        if self.observed_at.utcoffset() is None:
            raise ValueError("settlement observation must be timezone-aware")
        return self


class MediaCurrencyBucket(AipContractModel):
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    measured_minor: int = Field(ge=0)
    estimated_minor: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    adjustment_minor: int
    refund_minor: int = Field(ge=0)
    residual_minor: int | None


class MediaFinanceEvent(AipContractModel):
    tenant: TenantContext
    finance_id: str
    version: int = Field(ge=1)
    kind: MediaFinanceEventKind
    payload: dict
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    actor: str
    created_at: datetime


class MediaFinanceSnapshot(AipContractModel):
    tenant: TenantContext
    finance_id: str
    version: int = Field(ge=1)
    job_ref: ExactRevisionRef
    task_run_ref: ExactRevisionRef
    step_run_ref: ExactRevisionRef
    capacity_pool_ref: ExactRevisionRef
    capacity_reservation_ref: ExactRevisionRef
    budget_revision_ref: ExactRevisionRef
    budget_reservation_ref: ExactRevisionRef
    attempt_binding_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    projected_min_minor: int = Field(ge=0)
    projected_max_minor: int = Field(ge=0)
    projected_currency: str = Field(pattern=r"^[A-Z]{3}$")
    reservations_active: bool
    cancel_outcome: MediaCancelOutcome | None = None
    fee_conclusion: MediaFeeConclusion = MediaFeeConclusion.UNKNOWN
    usage_receipt_refs: list[ExactRevisionRef] = Field(default_factory=list, max_length=100)
    currency_buckets: list[MediaCurrencyBucket] = Field(default_factory=list, max_length=20)
    settlement_status: MediaSettlementStatus = MediaSettlementStatus.PENDING
    settlement_decision_ref: ExactRevisionRef | None = None
    blocker_codes: list[str] = Field(default_factory=list, max_length=64)
    expires_at: datetime
    created_by: str
    created_at: datetime
    updated_at: datetime
    external_effects_allowed: bool = False

    @model_validator(mode="after")
    def _conserves(self) -> "MediaFinanceSnapshot":
        currencies = [item.currency for item in self.currency_buckets]
        if currencies != sorted(set(currencies)):
            raise ValueError("currency buckets must be unique and sorted")
        if self.settlement_status is MediaSettlementStatus.SETTLED:
            if self.settlement_decision_ref is None or any(item.unknown_count for item in self.currency_buckets):
                raise ValueError("settled requires decision and no unknown usage")
        if self.external_effects_allowed:
            raise ValueError("W7-08 projection cannot authorize external effects")
        return self


class MediaFinanceListResponse(AipContractModel):
    tenant: TenantContext
    items: list[MediaFinanceSnapshot]
    count: int = Field(ge=0)

    @model_validator(mode="after")
    def _count(self) -> "MediaFinanceListResponse":
        if self.count != len(self.items):
            raise ValueError("media finance count drifted")
        return self


__all__ = [name for name in globals() if name.startswith("Media") or name.startswith("Prepare") or name.startswith("Observe") or name.startswith("Transition") or name.startswith("Bind") or name.startswith("Settle")]
