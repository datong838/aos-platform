"""Receipt-first, three-bucket budget reservation contracts."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import StrEnum
import hashlib
import json
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext


class BudgetReservationState(StrEnum):
    HELD = "held"
    SUBMITTED = "submitted"
    SETTLED = "settled"
    RELEASED = "released"
    UNKNOWN = "unknown"


class BudgetExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @field_validator("resource_type", "resource_id")
    @classmethod
    def _clean_identity(cls, value: str) -> str:
        cleaned = value.strip()
        if cleaned != value or not cleaned:
            raise ValueError("budget exact reference identity must be canonical")
        return cleaned


class BudgetBucketTarget(AipContractModel):
    kind: Literal["task", "daily", "pilot"]
    account_id: str = Field(min_length=1, max_length=200)
    period_start: datetime
    period_end: datetime

    @field_validator("account_id")
    @classmethod
    def _clean_account(cls, value: str) -> str:
        cleaned = value.strip()
        if cleaned != value or not cleaned:
            raise ValueError("budget account id must be canonical")
        return cleaned

    @model_validator(mode="after")
    def _bounded_period(self) -> "BudgetBucketTarget":
        if self.period_start.tzinfo is None or self.period_end.tzinfo is None:
            raise ValueError("budget bucket period requires timezone")
        if self.period_end <= self.period_start:
            raise ValueError("budget bucket period must be increasing")
        return self


class BudgetBucketAuthority(BudgetBucketTarget):
    currency: Literal["CNY"] = "CNY"
    limit_minor: int = Field(gt=0, le=100_000_000_000)


class ReserveBudgetRequest(AipContractModel):
    operation_id: str = Field(min_length=1, max_length=160)
    invocation_key: str = Field(min_length=1, max_length=200)
    task_ref: BudgetExactRef
    policy_ref: BudgetExactRef
    pricing_ref: BudgetExactRef
    approval_ref: BudgetExactRef
    currency: Literal["CNY"] = "CNY"
    upper_bound_minor: int = Field(gt=0, le=100_000_000)

    @field_validator("operation_id", "invocation_key")
    @classmethod
    def _clean_key(cls, value: str) -> str:
        cleaned = value.strip()
        if cleaned != value or not cleaned:
            raise ValueError("budget invocation key must be canonical")
        return cleaned

    @model_validator(mode="after")
    def _exact_authority(self) -> "ReserveBudgetRequest":
        expected = {
            "task_ref": "Task",
            "policy_ref": "BudgetRevision",
            "pricing_ref": "ModelPriceSnapshotRevision",
            "approval_ref": "ActionApprovalEvent",
        }
        for name, kind in expected.items():
            if getattr(self, name).resource_type != kind:
                raise ValueError(f"{name} must reference {kind}")
        return self

    def request_hash(self) -> str:
        payload = self.model_dump(mode="json", by_alias=True)
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class BudgetBucketSnapshot(AipContractModel):
    kind: Literal["task", "daily", "pilot"]
    account_id: str
    period_start: datetime
    period_end: datetime
    currency: Literal["CNY"]
    limit_minor: int = Field(gt=0)
    held_minor: int = Field(ge=0)
    submitted_minor: int = Field(ge=0)
    settled_minor: int = Field(ge=0)
    unknown_minor: int = Field(ge=0)


class BudgetReservationRevision(AipContractModel):
    tenant: TenantContext
    invocation_ref: BudgetExactRef
    reservation_ref: BudgetExactRef
    operation_id: str
    invocation_key: str
    task_ref: BudgetExactRef
    policy_ref: BudgetExactRef
    pricing_ref: BudgetExactRef
    approval_ref: BudgetExactRef
    state: BudgetReservationState
    currency: Literal["CNY"]
    upper_bound_minor: int = Field(gt=0)
    actual_minor: int | None = Field(default=None, ge=0)
    provider_request_receipt_ref: BudgetExactRef | None = None
    provider_receipt_ref: BudgetExactRef | None = None
    usage_receipt_refs: tuple[BudgetExactRef, ...] = ()
    reconciliation_evidence_ref: BudgetExactRef | None = None
    buckets: tuple[BudgetBucketSnapshot, BudgetBucketSnapshot, BudgetBucketSnapshot]
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    replayed: bool = False
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _state_shape(self) -> "BudgetReservationRevision":
        if self.invocation_ref.resource_type != "CapabilityInvocationRevision":
            raise ValueError("invocation_ref must reference CapabilityInvocationRevision")
        if self.reservation_ref.resource_type != "BudgetReservationRevision":
            raise ValueError("reservation_ref must reference BudgetReservationRevision")
        expected_refs = {
            "task_ref": "Task",
            "policy_ref": "BudgetRevision",
            "pricing_ref": "ModelPriceSnapshotRevision",
            "approval_ref": "ActionApprovalEvent",
        }
        for name, kind in expected_refs.items():
            if getattr(self, name).resource_type != kind:
                raise ValueError(f"{name} must reference {kind}")
        if (
            self.provider_request_receipt_ref is not None
            and self.provider_request_receipt_ref.resource_type
            != "CapabilityProviderRequestReceipt"
        ):
            raise ValueError(
                "provider_request_receipt_ref must reference CapabilityProviderRequestReceipt"
            )
        if (
            self.provider_receipt_ref is not None
            and self.provider_receipt_ref.resource_type != "CapabilityProviderReceipt"
        ):
            raise ValueError("provider_receipt_ref must reference CapabilityProviderReceipt")
        if any(item.resource_type != "UsageReceipt" for item in self.usage_receipt_refs):
            raise ValueError("usage_receipt_refs must reference UsageReceipt")
        if (
            self.reconciliation_evidence_ref is not None
            and self.reconciliation_evidence_ref.resource_type
            != "CapabilityProviderReceipt"
        ):
            raise ValueError(
                "reconciliation_evidence_ref must reference CapabilityProviderReceipt"
            )
        if tuple(item.kind for item in self.buckets) != ("task", "daily", "pilot"):
            raise ValueError("budget snapshot bucket order drifted")
        if self.state == BudgetReservationState.HELD:
            valid = (
                self.provider_request_receipt_ref is None
                and self.provider_receipt_ref is None
                and not self.usage_receipt_refs
                and self.actual_minor is None
                and self.reconciliation_evidence_ref is None
            )
        elif self.state in {BudgetReservationState.SUBMITTED, BudgetReservationState.UNKNOWN}:
            valid = (
                self.provider_request_receipt_ref is not None
                and self.provider_receipt_ref is None
                and not self.usage_receipt_refs
                and self.actual_minor is None
                and self.reconciliation_evidence_ref is None
            )
        elif self.state == BudgetReservationState.SETTLED:
            valid = (
                self.provider_request_receipt_ref is not None
                and self.provider_receipt_ref is not None
                and bool(self.usage_receipt_refs)
                and self.actual_minor is not None
                and self.actual_minor <= self.upper_bound_minor
            )
        else:
            valid = (
                self.provider_receipt_ref is None
                and not self.usage_receipt_refs
                and self.actual_minor is None
                and (
                    (
                        self.provider_request_receipt_ref is None
                        and self.reconciliation_evidence_ref is None
                    )
                    or (
                        self.provider_request_receipt_ref is not None
                        and self.reconciliation_evidence_ref is not None
                    )
                )
            )
        if not valid:
            raise ValueError("budget reservation state shape drifted")
        return self


def exact_ref_payload(value: BudgetExactRef | None) -> dict[str, Any] | None:
    return None if value is None else value.model_dump(mode="json", by_alias=True)


def derive_bucket_authorities(
    request: ReserveBudgetRequest,
    *,
    checked_at: datetime,
    budget_effective_from: datetime,
    budget_effective_until: datetime,
    daily_limit_minor: int,
    pilot_limit_minor: int,
    timezone_name: str = "Asia/Shanghai",
) -> tuple[BudgetBucketAuthority, BudgetBucketAuthority, BudgetBucketAuthority]:
    if any(
        value.tzinfo is None
        for value in (checked_at, budget_effective_from, budget_effective_until)
    ):
        raise ValueError("budget authority timestamps require timezone")
    if not budget_effective_from <= checked_at < budget_effective_until:
        raise ValueError("budget authority is outside its effective window")
    zone = ZoneInfo(timezone_name)
    local = checked_at.astimezone(zone)
    day_start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    month_start = day_start.replace(day=1)
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1)
    daily_start = max(day_start, budget_effective_from.astimezone(zone))
    daily_end = min(day_end, budget_effective_until.astimezone(zone))
    pilot_start = max(month_start, budget_effective_from.astimezone(zone))
    pilot_end = min(month_end, budget_effective_until.astimezone(zone))
    values = (
        ("task", f"{request.operation_id}:{request.task_ref.resource_id}",
         budget_effective_from, budget_effective_until, request.upper_bound_minor),
        ("daily", f"{request.policy_ref.resource_id}:daily",
         daily_start, daily_end, daily_limit_minor),
        ("pilot", f"{request.policy_ref.resource_id}:pilot",
         pilot_start, pilot_end, pilot_limit_minor),
    )
    return tuple(
        BudgetBucketAuthority(
            kind=kind,
            accountId=account_id,
            periodStart=start,
            periodEnd=end,
            currency="CNY",
            limitMinor=limit_minor,
        )
        for kind, account_id, start, end, limit_minor in values
    )


def usage_cost_minor(
    *, quantity: int | str | Decimal, unit_price_cny: str | Decimal, price_unit: int
) -> int:
    if type(price_unit) is not int or price_unit <= 0:
        raise ValueError("price_unit must be a positive integer")
    try:
        measured = Decimal(str(quantity))
        price = Decimal(str(unit_price_cny))
    except InvalidOperation as exc:
        raise ValueError("usage cost requires exact decimal values") from exc
    if measured < 0 or price < 0 or not measured.is_finite() or not price.is_finite():
        raise ValueError("usage cost values must be finite and non-negative")
    minor = (measured * price * Decimal(100) / Decimal(price_unit)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    if minor > Decimal(9_223_372_036_854_775_807):
        raise ValueError("usage cost exceeds bigint authority")
    return int(minor)


__all__ = [
    "BudgetBucketAuthority",
    "BudgetBucketSnapshot",
    "BudgetBucketTarget",
    "BudgetExactRef",
    "BudgetReservationRevision",
    "BudgetReservationState",
    "ReserveBudgetRequest",
    "derive_bucket_authorities",
    "usage_cost_minor",
    "exact_ref_payload",
]
