"""Strict privacy-minimized contracts for the ecommerce customer read model."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext

CUSTOMER_VIEW_SCHEMA_VERSION = "aos.ecommerce-workshop.customer-view/v1"


class CustomerViewId(StrEnum):
    CUSTOMER = "customer"
    SEGMENT = "segment"
    JOURNEY = "journey"
    DIALOGUE = "dialogue"


class CustomerReadinessAxis(StrEnum):
    CUSTOMER_LITE = "customer_lite"
    CONSENT = "consent"
    SEGMENT = "segment"
    JOURNEY = "journey"
    DIALOGUE = "dialogue"
    OUTREACH_BATCH = "outreach_batch"


class CustomerExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    receipt_id: str = Field(min_length=1, max_length=200)


class CustomerBlocker(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    dependency: str = Field(min_length=1, max_length=180)
    required_action: str = Field(min_length=1, max_length=500)


class CustomerAxisReadiness(AipContractModel):
    axis: CustomerReadinessAxis
    status: Literal["ready", "blocked", "unknown", "not_applicable"]
    exact_ref: CustomerExactRef | None = None
    blockers: list[CustomerBlocker] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _honest_status(self) -> CustomerAxisReadiness:
        if self.status == "ready" and (self.exact_ref is None or self.blockers):
            raise ValueError("ready customer axis requires exact ref and no blockers")
        if self.status in {"blocked", "unknown"} and (self.exact_ref is not None or not self.blockers):
            raise ValueError("non-ready customer axis requires blockers and no exact ref")
        if self.status == "not_applicable" and (self.exact_ref is not None or self.blockers):
            raise ValueError("not-applicable customer axis cannot attach evidence")
        return self


class CustomerProjection(AipContractModel):
    customer_ref: CustomerExactRef
    purpose: str = Field(min_length=1, max_length=160)
    disclosure: Literal["allowed", "blocked", "unknown"]
    freshness: Literal["fresh", "stale", "unknown"]
    quality: Literal["pass", "fail", "unknown"]
    consent: Literal["granted", "withdrawn", "expired", "conflict", "unknown"]
    retention: Literal["active", "expired", "unknown"]
    k_anonymity_satisfied: bool | None = None
    original_refs: list[CustomerExactRef] = Field(default_factory=list, max_length=100)
    blockers: list[CustomerBlocker] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _purpose_scoped(self) -> CustomerProjection:
        if self.disclosure == "allowed" and (self.freshness != "fresh" or self.quality != "pass" or self.consent != "granted" or self.retention != "active" or self.blockers):
            raise ValueError("allowed disclosure requires fresh quality consent and retention evidence")
        if self.disclosure != "allowed" and not self.blockers:
            raise ValueError("non-allowed disclosure requires blockers")
        identities = [(item.resource_type, item.resource_id, item.revision, item.content_hash, item.receipt_id) for item in self.original_refs]
        if len(identities) != len(set(identities)):
            raise ValueError("customer originals must be unique")
        return self


class CustomerCountLedger(AipContractModel):
    input: int = Field(ge=0)
    eligible: int = Field(ge=0)
    excluded: int = Field(ge=0)
    unknown: int = Field(ge=0)
    deduplicated: int = Field(ge=0)

    @model_validator(mode="after")
    def _conserves(self) -> CustomerCountLedger:
        if self.input != self.eligible + self.excluded + self.unknown + self.deduplicated:
            raise ValueError("customer ledger must conserve input")
        return self


class CustomerViewSlice(AipContractModel):
    view_id: CustomerViewId
    status: Literal["ready", "blocked"]
    resource_revision: int = Field(ge=1)
    data_cutoff: datetime
    readiness_axes: list[CustomerAxisReadiness] = Field(min_length=6, max_length=6)
    items: list[CustomerProjection] = Field(default_factory=list, max_length=100)
    authority_refs: list[CustomerExactRef] = Field(default_factory=list, max_length=100)
    blockers: list[CustomerBlocker] = Field(default_factory=list, max_length=20)
    count_ledger: CustomerCountLedger

    @model_validator(mode="after")
    def _canonical_and_honest(self) -> CustomerViewSlice:
        if self.data_cutoff.utcoffset() is None or [item.axis for item in self.readiness_axes] != list(CustomerReadinessAxis):
            raise ValueError("customer view requires canonical axes and timezone cutoff")
        if self.count_ledger.input - self.count_ledger.deduplicated != len(self.items):
            raise ValueError("customer ledger does not match items")
        if self.status == "ready" and (self.blockers or any(item.status in {"blocked", "unknown"} for item in self.readiness_axes)):
            raise ValueError("ready customer view cannot hide blocked axes")
        if self.status == "blocked" and not self.blockers:
            raise ValueError("blocked customer view requires blockers")
        return self


class CustomerPageInfo(AipContractModel):
    limit: Literal[100] = 100
    count: int = Field(ge=0, le=400)
    has_more: Literal[False] = False
    next_cursor: None = None


class WorkshopCustomerViewEnvelope(AipContractModel):
    schema_version: Literal[CUSTOMER_VIEW_SCHEMA_VERSION] = CUSTOMER_VIEW_SCHEMA_VERSION
    tenant: TenantContext
    resource_revision: int = Field(ge=1)
    evaluated_at: datetime
    data_cutoff: datetime
    readiness: Literal["degraded"] = "degraded"
    views: list[CustomerViewSlice] = Field(min_length=4, max_length=4)
    page: CustomerPageInfo

    @field_validator("evaluated_at", "data_cutoff")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("customer envelope timestamps require timezone")
        return value

    @model_validator(mode="after")
    def _canonical_shape(self) -> WorkshopCustomerViewEnvelope:
        if [item.view_id for item in self.views] != list(CustomerViewId):
            raise ValueError("customer views require canonical order")
        if any(item.data_cutoff != self.data_cutoff or item.resource_revision != self.resource_revision for item in self.views):
            raise ValueError("customer views require one revision and cutoff")
        if self.page.count != sum(len(item.items) for item in self.views):
            raise ValueError("customer page count must equal items")
        return self


__all__ = ["CUSTOMER_VIEW_SCHEMA_VERSION", "CustomerAxisReadiness", "CustomerBlocker", "CustomerCountLedger", "CustomerExactRef", "CustomerPageInfo", "CustomerProjection", "CustomerReadinessAxis", "CustomerViewId", "CustomerViewSlice", "WorkshopCustomerViewEnvelope"]
