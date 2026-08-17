"""Canonical tenant-scoped BudgetRevision contracts for AIP runtime gates."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext


class BudgetLifecycle(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"


class BudgetRevisionCreate(AipContractModel):
    budget_id: str = Field(min_length=1, max_length=160)
    revision: int = Field(ge=1)
    environment: Literal["development"] = "development"
    currency: Literal["CNY"] = "CNY"
    daily_limit_minor: int = Field(gt=0)
    monthly_limit_minor: int = Field(gt=0)
    alert_threshold_pct: int = Field(ge=1, le=100)
    hard_stop: Literal[True] = True
    unknown_usage_behavior: Literal["block"] = "block"
    effective_from: datetime
    effective_until: datetime
    owner: str = Field(min_length=1, max_length=160)
    over_budget_approver: str = Field(min_length=1, max_length=160)
    lifecycle: BudgetLifecycle

    @field_validator("budget_id", "owner", "over_budget_approver")
    @classmethod
    def _clean_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("budget authority fields must not be blank")
        return cleaned

    @model_validator(mode="after")
    def _safe_window(self) -> "BudgetRevisionCreate":
        if self.effective_from.tzinfo is None or self.effective_until.tzinfo is None:
            raise ValueError("effectiveFrom and effectiveUntil require timezone")
        if self.effective_until <= self.effective_from:
            raise ValueError("effectiveUntil must be after effectiveFrom")
        if self.monthly_limit_minor < self.daily_limit_minor:
            raise ValueError("monthlyLimitMinor must be at least dailyLimitMinor")
        return self


class BudgetRevision(BudgetRevisionCreate):
    tenant: TenantContext
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime
