"""Frozen platform-neutral contracts for ecommerce prerequisites (228-EC)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from enum import StrEnum
import json
import re
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator


EC_CAPABILITY_IDS = frozenset(
    {
        "ec.connector.rest.read",
        "ec.auth.oauth2",
        "ec.auth.signed-request",
        "ec.connector.graphql.read",
        "ec.connector.webhook.receive",
        "ec.sync.incremental",
        "ec.ontology.core7",
        "ec.pipeline.evidence",
    }
)
EC_INDEPENDENT_PLATFORM_COUNT = 7
EC_SCHEME_DIRECTORY_COUNT = 8
EC_PLANNED_ENTRY_COUNT = 9


class ContractViolation(ValueError):
    """A stable, caller-safe public contract violation."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class TaskStatus(StrEnum):
    PENDING = "pending"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


TERMINAL_TASK_STATUSES = frozenset(
    {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.ROLLED_BACK}
)
_LEGACY_TASK_STATUS = {"created": TaskStatus.PENDING}
_TASK_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.PENDING: frozenset({TaskStatus.PLANNING}),
    TaskStatus.PLANNING: frozenset({TaskStatus.AWAITING_APPROVAL, TaskStatus.CANCELLED}),
    TaskStatus.AWAITING_APPROVAL: frozenset({TaskStatus.APPROVED, TaskStatus.CANCELLED}),
    TaskStatus.APPROVED: frozenset({TaskStatus.EXECUTING, TaskStatus.CANCELLED}),
    TaskStatus.EXECUTING: frozenset(
        {TaskStatus.PAUSED, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
    ),
    TaskStatus.PAUSED: frozenset({TaskStatus.EXECUTING}),
    TaskStatus.COMPLETED: frozenset({TaskStatus.ROLLED_BACK}),
    TaskStatus.FAILED: frozenset(),
    TaskStatus.CANCELLED: frozenset(),
    TaskStatus.ROLLED_BACK: frozenset(),
}


def normalize_task_status(value: str | TaskStatus) -> TaskStatus:
    if isinstance(value, TaskStatus):
        return value
    normalized = str(value).strip().lower()
    if normalized in _LEGACY_TASK_STATUS:
        return _LEGACY_TASK_STATUS[normalized]
    try:
        return TaskStatus(normalized)
    except ValueError as exc:
        raise ContractViolation("TASK_STATUS_UNKNOWN", "unknown task status") from exc


def transition_task_status(
    current: str | TaskStatus, target: str | TaskStatus
) -> TaskStatus:
    source = normalize_task_status(current)
    destination = normalize_task_status(target)
    if source == destination:
        return source
    if destination not in _TASK_TRANSITIONS[source]:
        raise ContractViolation(
            "TASK_STATUS_CONFLICT",
            f"task status cannot transition from {source.value} to {destination.value}",
        )
    return destination


class ExternalIdentityKey(BaseModel):
    model_config = ConfigDict(frozen=True)

    org_id: str
    workspace_id: str
    platform: str
    shop_or_marketplace_id: str
    external_id: str

    @field_validator("org_id", "workspace_id", "shop_or_marketplace_id", "external_id")
    @classmethod
    def _nonempty_id(cls, value: str) -> str:
        cleaned = str(value).strip()
        if not cleaned:
            raise ValueError("identity fields must not be empty")
        return cleaned

    @field_validator("platform")
    @classmethod
    def _platform(cls, value: str) -> str:
        cleaned = str(value).strip().lower()
        if not cleaned:
            raise ValueError("platform must not be empty")
        return cleaned

    def public_key(self) -> tuple[str, str, str, str]:
        return (
            self.workspace_id,
            self.platform,
            self.shop_or_marketplace_id,
            self.external_id,
        )

    def scoped_key(self) -> tuple[str, str, str, str, str]:
        return (self.org_id, *self.public_key())


_CURRENCY_SCALES = {"CNY": 2, "USD": 2, "JPY": 0}


class Money(BaseModel):
    model_config = ConfigDict(frozen=True)

    amount: Decimal
    currency: str
    scale: int

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        currency = str(data.get("currency", "")).strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("currency must be a three-letter ISO 4217 code")
        scale = data.get("scale", _CURRENCY_SCALES.get(currency))
        if scale is None:
            raise ValueError("unknown currency requires an explicit scale")
        if isinstance(data.get("amount"), float):
            raise ValueError("binary float money input is forbidden")
        try:
            amount = Decimal(str(data.get("amount")))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("invalid decimal amount") from exc
        scale = int(scale)
        if scale < 0 or scale > 9:
            raise ValueError("scale must be between 0 and 9")
        quantum = Decimal(1).scaleb(-scale)
        data.update(amount=amount.quantize(quantum, rounding=ROUND_HALF_EVEN), currency=currency, scale=scale)
        return data

    @field_serializer("amount")
    def _serialize_amount(self, amount: Decimal) -> str:
        return f"{amount:.{self.scale}f}"

    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency or self.scale != other.scale:
            raise ContractViolation("MONEY_CURRENCY_MISMATCH", "money currencies or scales differ")
        return Money(amount=self.amount + other.amount, currency=self.currency, scale=self.scale)


class MoneyBag(BaseModel):
    amounts: dict[str, Money] = Field(default_factory=dict)

    def add(self, money: Money) -> "MoneyBag":
        current = self.amounts.get(money.currency)
        updated = dict(self.amounts)
        updated[money.currency] = money if current is None else current + money
        return MoneyBag(amounts=updated)


class ExchangeRate(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_currency: str
    target_currency: str
    rate: Decimal
    source: str
    as_of: datetime
    target_scale: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_rate(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        if isinstance(data.get("rate"), float):
            raise ValueError("binary float exchange rate is forbidden")
        try:
            data["rate"] = Decimal(str(data.get("rate")))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("invalid decimal exchange rate") from exc
        if data["rate"] <= 0:
            raise ValueError("exchange rate must be positive")
        for field in ("source_currency", "target_currency"):
            data[field] = str(data.get(field, "")).strip().upper()
            if not re.fullmatch(r"[A-Z]{3}", data[field]):
                raise ValueError(f"{field} must be a three-letter currency code")
        data["source"] = str(data.get("source", "")).strip()
        if not data["source"]:
            raise ValueError("exchange rate source is required")
        return data

    @field_validator("as_of")
    @classmethod
    def _aware_as_of(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("exchange rate as_of must include timezone")
        return value.astimezone(timezone.utc)

    def convert(self, money: Money) -> Money:
        if money.currency != self.source_currency:
            raise ContractViolation("FX_SOURCE_MISMATCH", "money currency differs from exchange rate source")
        scale = self.target_scale
        if scale is None:
            scale = _CURRENCY_SCALES.get(self.target_currency)
        if scale is None:
            raise ContractViolation("FX_TARGET_SCALE_REQUIRED", "unknown target currency requires scale")
        return Money(
            amount=money.amount * self.rate,
            currency=self.target_currency,
            scale=scale,
        )


class ZonedInstant(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_value: str
    source_timezone: str
    utc: datetime

    @classmethod
    def parse(cls, value: str) -> "ZonedInstant":
        raw = str(value).strip()
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ContractViolation("TIME_INVALID", "time must be ISO8601") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ContractViolation("TIME_NAIVE", "time must include timezone")
        offset = parsed.strftime("%z")
        source_timezone = "Z" if offset == "+0000" and raw.endswith("Z") else parsed.strftime("%z")
        return cls(source_value=raw, source_timezone=source_timezone, utc=parsed.astimezone(timezone.utc))

    def canonical_utc(self) -> str:
        return self.utc.isoformat(timespec="microseconds").replace("+00:00", "Z")


class StableCursor(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_updated_at_utc: datetime
    external_id: str

    @field_validator("source_updated_at_utc")
    @classmethod
    def _aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("cursor time must include timezone")
        return value.astimezone(timezone.utc)

    @field_validator("external_id")
    @classmethod
    def _cursor_id(cls, value: str) -> str:
        cleaned = str(value).strip()
        if not cleaned:
            raise ValueError("external_id must not be empty")
        return cleaned

    def sort_key(self) -> tuple[datetime, str]:
        return self.source_updated_at_utc, self.external_id

    def encode(self) -> str:
        payload = [
            self.source_updated_at_utc.isoformat(timespec="microseconds").replace("+00:00", "Z"),
            self.external_id,
        ]
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def decode(cls, value: str) -> "StableCursor":
        try:
            timestamp, external_id = json.loads(value)
            parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ContractViolation("CURSOR_INVALID", "stable cursor is invalid") from exc
        return cls(source_updated_at_utc=parsed, external_id=str(external_id))


class ForwardEnumValue(BaseModel):
    model_config = ConfigDict(frozen=True)

    canonical_value: str
    raw_status: str
    unknown: bool

    @classmethod
    def from_raw(cls, raw: Any, mapping: Mapping[str, str]) -> "ForwardEnumValue":
        raw_status = "" if raw is None else str(raw)
        canonical = mapping.get(raw_status)
        return cls(
            canonical_value=canonical if canonical is not None else "unknown",
            raw_status=raw_status,
            unknown=canonical is None,
        )


_SENSITIVE_KEYS = re.compile(
    r"authorization|token|secret|password|passwd|cookie|api[_-]?key|email|phone|mobile|address|id[_-]?card|ssn",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+\-/=]+")
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_SECRET = re.compile(r"\b(?:sk|pk)-[A-Za-z0-9_-]{8,}\b")


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if _SENSITIVE_KEYS.search(str(key)) else redact_sensitive(child)
            for key, child in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [redact_sensitive(child) for child in value]
    if isinstance(value, str):
        result = _BEARER.sub("Bearer [REDACTED]", value)
        result = _EMAIL.sub("[REDACTED]", result)
        result = _PHONE.sub("[REDACTED]", result)
        return _SECRET.sub("[REDACTED]", result)
    return value
