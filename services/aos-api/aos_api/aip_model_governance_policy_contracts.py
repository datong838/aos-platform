"""Immutable quota and budget-policy contracts for AIP model governance."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import AipContractModel, TenantContext


class ModelGovernancePolicyLifecycle(StrEnum):
    DRAFT = "draft"
    BLOCKED = "blocked"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ModelGovernancePolicyCreate(AipContractModel):
    policy_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    environment: Literal["development"] = "development"
    effective_from: datetime
    effective_until: datetime
    owner: str = Field(min_length=1, max_length=160)
    approval_ref: str = Field(min_length=1, max_length=240)
    lifecycle: ModelGovernancePolicyLifecycle

    @field_validator("policy_id", "owner", "approval_ref")
    @classmethod
    def _clean_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("model governance policy identity fields must not be blank")
        return cleaned

    @model_validator(mode="after")
    def _valid_window(self) -> "ModelGovernancePolicyCreate":
        if self.effective_from.tzinfo is None or self.effective_until.tzinfo is None:
            raise ValueError("effective policy window requires timezone")
        if self.effective_until <= self.effective_from:
            raise ValueError("effectiveUntil must be after effectiveFrom")
        return self


class QuotaPolicyRevisionCreate(ModelGovernancePolicyCreate):
    max_concurrency: int = Field(ge=1, le=2)
    max_input_tokens: int = Field(ge=1, le=8000)
    max_output_tokens: int = Field(ge=1, le=2000)
    hourly_request_limit: int = Field(ge=1, le=50)
    daily_request_limit: int = Field(ge=1, le=200)
    reservation_lease_seconds: Literal[60] = 60
    overflow_behavior: Literal["queue", "reject"]
    allow_public_provider_fallback: Literal[False] = False
    allow_auto_scale: Literal[False] = False

    @model_validator(mode="after")
    def _daily_covers_hourly(self) -> "QuotaPolicyRevisionCreate":
        if self.daily_request_limit < self.hourly_request_limit:
            raise ValueError("dailyRequestLimit must be at least hourlyRequestLimit")
        return self


class BudgetPolicyRevisionCreate(ModelGovernancePolicyCreate):
    budget_revision_ref: VersionedAssetRef
    currency: Literal["CNY"] = "CNY"
    hard_stop: Literal[True] = True
    unknown_usage_behavior: Literal["block"] = "block"
    unknown_price_behavior: Literal["block"] = "block"
    allow_zero_price: bool = False
    zero_price_approval_ref: str | None = Field(default=None, max_length=240)

    @model_validator(mode="after")
    def _safe_budget_policy(self) -> "BudgetPolicyRevisionCreate":
        if self.budget_revision_ref.asset_type != "BudgetRevision":
            raise ValueError("budgetRevisionRef must reference BudgetRevision")
        if self.zero_price_approval_ref is not None:
            self.zero_price_approval_ref = self.zero_price_approval_ref.strip() or None
        if self.allow_zero_price and not self.zero_price_approval_ref:
            raise ValueError("allowZeroPrice requires zeroPriceApprovalRef")
        if not self.allow_zero_price and self.zero_price_approval_ref:
            raise ValueError("zeroPriceApprovalRef is only valid when allowZeroPrice=true")
        return self


class QuotaPolicyRevision(QuotaPolicyRevisionCreate):
    tenant: TenantContext
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime


class BudgetPolicyRevision(BudgetPolicyRevisionCreate):
    tenant: TenantContext
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime
