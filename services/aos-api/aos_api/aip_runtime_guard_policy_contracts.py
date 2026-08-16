"""Tenant-scoped immutable runtime egress and data-classification contracts."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext


APPROVED_DATA_CLASSIFICATIONS = {
    "public_catalog",
    "deidentified_order_aggregate",
    "approved_development_sample",
    "approved_internal_knowledge",
}
REQUIRED_PROHIBITED_CLASSIFICATIONS = {
    "direct_pii",
    "raw_order_detail",
    "customer_conversation",
    "credential",
    "commercial_sensitive",
    "cross_tenant",
    "unknown",
}


class GuardPolicyLifecycle(StrEnum):
    DRAFT = "draft"
    BLOCKED = "blocked"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"


class RegionState(StrEnum):
    UNKNOWN = "unknown"
    CONFIRMED = "confirmed"


class GuardPolicyCreate(AipContractModel):
    policy_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    environment: Literal["development"] = "development"
    effective_from: datetime
    effective_until: datetime
    owner: str = Field(min_length=1, max_length=160)
    approval_ref: str = Field(min_length=1, max_length=240)
    lifecycle: GuardPolicyLifecycle

    @field_validator("policy_id", "owner", "approval_ref")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("guard policy identity fields must not be blank")
        return cleaned

    @model_validator(mode="after")
    def _valid_window(self) -> "GuardPolicyCreate":
        if self.effective_from.tzinfo is None or self.effective_until.tzinfo is None:
            raise ValueError("effective policy window requires timezone")
        if self.effective_until <= self.effective_from:
            raise ValueError("effectiveUntil must be after effectiveFrom")
        return self


class EgressPolicyRevisionCreate(GuardPolicyCreate):
    allowed_schemes: list[Literal["https"]] = Field(min_length=1, max_length=1)
    allowed_hosts: list[Literal["apihub.agnes-ai.com"]] = Field(min_length=1, max_length=1)
    allowed_ports: list[Literal[443]] = Field(min_length=1, max_length=1)
    allow_public_fallback: Literal[False] = False
    unknown_destination_behavior: Literal["block"] = "block"
    region_state: RegionState
    region: str | None = Field(default=None, max_length=120)

    @field_validator("allowed_schemes", "allowed_hosts", "allowed_ports")
    @classmethod
    def _unique_boundary(cls, values: list) -> list:
        if len(values) != len(set(values)):
            raise ValueError("egress allowlist values must be unique")
        return values

    @model_validator(mode="after")
    def _active_requires_confirmed_region(self) -> "EgressPolicyRevisionCreate":
        if self.region is not None:
            self.region = self.region.strip() or None
        if self.lifecycle is GuardPolicyLifecycle.ACTIVE:
            if self.region_state is not RegionState.CONFIRMED or not self.region:
                raise ValueError("active egress policy requires confirmed region")
        elif self.region_state is RegionState.CONFIRMED and not self.region:
            raise ValueError("confirmed region state requires region")
        return self


class DataClassificationPolicyRevisionCreate(GuardPolicyCreate):
    allowed_classifications: list[str] = Field(min_length=1, max_length=16)
    prohibited_classifications: list[str] = Field(min_length=7, max_length=32)
    deny_unknown: Literal[True] = True
    allow_direct_pii: Literal[False] = False
    allow_commercial_sensitive: Literal[False] = False
    allow_cross_tenant: Literal[False] = False

    @model_validator(mode="after")
    def _approved_classifications_only(self) -> "DataClassificationPolicyRevisionCreate":
        allowed = [value.strip() for value in self.allowed_classifications]
        prohibited = [value.strip() for value in self.prohibited_classifications]
        if any(not value for value in (*allowed, *prohibited)):
            raise ValueError("data classifications must not be blank")
        if len(allowed) != len(set(allowed)) or len(prohibited) != len(set(prohibited)):
            raise ValueError("data classifications must be unique")
        if not set(allowed) <= APPROVED_DATA_CLASSIFICATIONS:
            raise ValueError("allowed data classification is not approved")
        if not REQUIRED_PROHIBITED_CLASSIFICATIONS <= set(prohibited):
            raise ValueError("required prohibited data classifications are incomplete")
        if set(allowed) & set(prohibited):
            raise ValueError("allowed and prohibited classifications overlap")
        self.allowed_classifications = allowed
        self.prohibited_classifications = prohibited
        return self


class EgressPolicyRevision(EgressPolicyRevisionCreate):
    tenant: TenantContext
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime


class DataClassificationPolicyRevision(DataClassificationPolicyRevisionCreate):
    tenant: TenantContext
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime
