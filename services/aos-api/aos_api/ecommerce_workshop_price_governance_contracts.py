"""Strict read-only contracts for the ecommerce price-governance aggregate."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext

PRICE_GOVERNANCE_SCHEMA_VERSION = "aos.ecommerce-workshop.price-governance-view/v1"


class PriceGovernanceViewId(StrEnum):
    GOVERNANCE = "governance"
    COMPETITOR = "competitor"
    SCHEDULE = "schedule"


class PriceReadinessAxis(StrEnum):
    COLLECTION = "collection"
    MATCH = "match"
    POLICY_CASE = "policy_case"
    NOTIFICATION = "notification"
    ADVICE_HANDOFF = "advice_handoff"
    REPRICING = "repricing"


class PriceExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    receipt_id: str = Field(min_length=1, max_length=200)


class PriceBlocker(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    dependency: str = Field(min_length=1, max_length=180)
    required_action: str = Field(min_length=1, max_length=500)


class PriceAxisReadiness(AipContractModel):
    axis: PriceReadinessAxis
    status: Literal["ready", "blocked", "unknown", "not_applicable", "disabled"]
    exact_ref: PriceExactRef | None = None
    blockers: list[PriceBlocker] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _honest_status(self) -> PriceAxisReadiness:
        if self.status == "ready" and (self.exact_ref is None or self.blockers):
            raise ValueError("ready price axis requires exact ref and no blockers")
        if self.status in {"blocked", "unknown", "disabled"} and (self.exact_ref is not None or not self.blockers):
            raise ValueError("non-ready price axis requires blockers and no exact ref")
        if self.status == "not_applicable" and (self.exact_ref is not None or self.blockers):
            raise ValueError("not-applicable price axis cannot attach refs or blockers")
        if self.axis is PriceReadinessAxis.REPRICING and self.status != "disabled":
            raise ValueError("repricing remains disabled in W2")
        return self


class PriceQuoteBasis(AipContractModel):
    basis: Literal["list", "landed"]
    sku_ref: PriceExactRef
    bundle_ref: PriceExactRef | None = None
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=80)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    tax: Literal["included", "excluded", "unknown"]
    shipping: Literal["included", "excluded", "unknown"]
    promotion_condition: str = Field(min_length=1, max_length=500)
    effective_from: datetime
    effective_until: datetime | None = None

    @model_validator(mode="after")
    def _valid_window(self) -> PriceQuoteBasis:
        if not isfinite(self.quantity):
            raise ValueError("price quantity must be finite")
        if self.effective_from.utcoffset() is None or (self.effective_until is not None and self.effective_until.utcoffset() is None):
            raise ValueError("price effective window requires timezone")
        if self.effective_until is not None and self.effective_until <= self.effective_from:
            raise ValueError("price effective window is inverted")
        return self


class PriceObservationProjection(AipContractModel):
    observation_ref: PriceExactRef
    market: str = Field(min_length=1, max_length=120)
    amount: float | None = None
    quote_basis: PriceQuoteBasis
    observed_at: datetime
    freshness: Literal["fresh", "stale", "unknown"]
    license: Literal["allowed", "denied", "unknown"]
    comparability: Literal["comparable", "not_comparable", "unknown"]
    match_status: Literal["confirmed", "preliminary", "not_matched", "unknown"]
    original_refs: list[PriceExactRef] = Field(min_length=1, max_length=100)
    merged_original_refs: list[PriceExactRef] = Field(default_factory=list, max_length=100)
    blockers: list[PriceBlocker] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _honest_observation(self) -> PriceObservationProjection:
        if self.observed_at.utcoffset() is None:
            raise ValueError("price observation requires timezone")
        if self.amount is not None and not isfinite(self.amount):
            raise ValueError("price amount must be finite")
        identities = [(item.resource_type, item.resource_id, item.revision, item.content_hash, item.receipt_id) for item in [*self.original_refs, *self.merged_original_refs]]
        if len(identities) != len(set(identities)):
            raise ValueError("price originals must be unique")
        if self.comparability == "comparable" and (self.amount is None or self.amount < 0 or self.freshness != "fresh" or self.license != "allowed" or self.match_status != "confirmed" or self.blockers):
            raise ValueError("comparable price requires fresh licensed confirmed evidence")
        if self.comparability == "unknown" and self.amount is not None:
            raise ValueError("unknown price cannot expose zero or another value")
        return self


class PriceCountLedger(AipContractModel):
    input: int = Field(ge=0)
    eligible: int = Field(ge=0)
    excluded: int = Field(ge=0)
    needs_review: int = Field(ge=0)
    unknown: int = Field(ge=0)
    deduplicated: int = Field(ge=0)

    @model_validator(mode="after")
    def _conserves(self) -> PriceCountLedger:
        if self.input != self.eligible + self.excluded + self.needs_review + self.unknown + self.deduplicated:
            raise ValueError("price ledger must conserve input")
        return self


class PriceGovernanceViewSlice(AipContractModel):
    view_id: PriceGovernanceViewId
    status: Literal["ready", "blocked"]
    resource_revision: int = Field(ge=1)
    data_cutoff: datetime
    readiness_axes: list[PriceAxisReadiness] = Field(min_length=6, max_length=6)
    observations: list[PriceObservationProjection] = Field(default_factory=list, max_length=100)
    authority_refs: list[PriceExactRef] = Field(default_factory=list, max_length=100)
    blockers: list[PriceBlocker] = Field(default_factory=list, max_length=20)
    count_ledger: PriceCountLedger

    @model_validator(mode="after")
    def _canonical_and_honest(self) -> PriceGovernanceViewSlice:
        if self.data_cutoff.utcoffset() is None or [item.axis for item in self.readiness_axes] != list(PriceReadinessAxis):
            raise ValueError("price view requires canonical axes and timezone cutoff")
        if self.count_ledger.input - self.count_ledger.deduplicated != len(self.observations):
            raise ValueError("price observation ledger does not match projection")
        if self.status == "ready" and (self.blockers or any(item.status in {"blocked", "unknown"} for item in self.readiness_axes)):
            raise ValueError("ready price view cannot hide blocked axes")
        if self.status == "blocked" and not self.blockers:
            raise ValueError("blocked price view requires blockers")
        return self


class PricePageInfo(AipContractModel):
    limit: Literal[100] = 100
    count: int = Field(ge=0, le=300)
    has_more: Literal[False] = False
    next_cursor: None = None


class WorkshopPriceGovernanceViewEnvelope(AipContractModel):
    schema_version: Literal[PRICE_GOVERNANCE_SCHEMA_VERSION] = PRICE_GOVERNANCE_SCHEMA_VERSION
    tenant: TenantContext
    resource_revision: int = Field(ge=1)
    evaluated_at: datetime
    data_cutoff: datetime
    readiness: Literal["degraded"] = "degraded"
    views: list[PriceGovernanceViewSlice] = Field(min_length=3, max_length=3)
    page: PricePageInfo

    @field_validator("evaluated_at", "data_cutoff")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("price envelope timestamps require timezone")
        return value

    @model_validator(mode="after")
    def _canonical_shape(self) -> WorkshopPriceGovernanceViewEnvelope:
        if [item.view_id for item in self.views] != list(PriceGovernanceViewId):
            raise ValueError("price views require canonical order")
        if any(item.data_cutoff != self.data_cutoff or item.resource_revision != self.resource_revision for item in self.views):
            raise ValueError("price views require one revision and cutoff")
        if self.page.count != sum(len(item.observations) for item in self.views):
            raise ValueError("price page count must equal observations")
        return self


__all__ = ["PRICE_GOVERNANCE_SCHEMA_VERSION", "PriceAxisReadiness", "PriceBlocker", "PriceCountLedger", "PriceExactRef", "PriceGovernanceViewId", "PriceGovernanceViewSlice", "PriceObservationProjection", "PricePageInfo", "PriceQuoteBasis", "PriceReadinessAxis", "WorkshopPriceGovernanceViewEnvelope"]
