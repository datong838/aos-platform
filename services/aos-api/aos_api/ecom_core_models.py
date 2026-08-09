"""Platform-neutral core-7 ecommerce ontology and incremental contracts.

Public identity, money, time and enum parsing belong to ``public_contracts``.
This module only projects an already validated public identity into the
internal tenant-safe storage key used by the consistency store.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aos_api.public_contracts import (
    ExternalIdentityKey,
    ForwardEnumValue,
    Money,
    StableCursor,
    ZonedInstant,
)


CORE_OBJECT_TYPES = frozenset(
    {
        "Shop", "Product", "ProductSku", "Category",
        "Order", "OrderLine", "Shipment",
        "CustomerLite",  # D1.5: 增长扩展 OT（隐私最小化，frozen/02 §P08）
        # D4: 横切底座 + 评价 + 支付（frozen/02 §P09~P12）
        "Weapp", "SystemConfig", "ProductReview", "Payment",
    }
)

CORE_LINK_TYPES: dict[str, tuple[str, str]] = {
    "Order.lines": ("Order", "OrderLine"),
    "OrderLine.ofSku": ("OrderLine", "ProductSku"),
    "OrderLine.ofProduct": ("OrderLine", "Product"),
    "ProductSku.ofProduct": ("ProductSku", "Product"),
    "Product.inCategory": ("Product", "Category"),
    "Shop.sellsProduct": ("Shop", "Product"),
    "Order.fulfilledBy": ("Order", "Shipment"),
    # D1.5: Order → CustomerLite 关联（隐私最小化，frozen/02 §P08）
    "Order.placedByLite": ("Order", "CustomerLite"),
    # D4: 6 条新 Link（frozen/02 §3.5；Product.inCategory 已在 D1 落地不重复注册）
    "Shop.hasWeapp": ("Shop", "Weapp"),            # site_id 关联
    "Product.hasReview": ("Product", "ProductReview"),  # goods_id 关联
    "ProductReview.ofSku": ("ProductReview", "ProductSku"),  # sku_id 关联
    "ProductReview.byMember": ("ProductReview", "CustomerLite"),  # member_id 关联
    "Order.hasPayment": ("Order", "Payment"),      # out_trade_no 或 relate_id≈order_id
    "Order.fromWeapp": ("Order", "Weapp"),          # weapp_id 关联
}

DERIVED_PROPERTIES: dict[str, frozenset[str]] = {
    "Product": frozenset({"quality_score"}),
    "ProductSku": frozenset({"stock_health"}),
    "Order": frozenset({"risk_score"}),
    "Shipment": frozenset({"overdue_hours"}),
    "CustomerLite": frozenset({"order_count", "last_order_days"}),
    "ProductReview": frozenset({"review_quality_bucket"}),
    "Payment": frozenset({"pay_duration_min"}),
}

REQUIRED_PROPERTIES: dict[str, frozenset[str]] = {
    "Shop": frozenset({"name", "status", "currency", "timezone"}),
    "Product": frozenset(
        {"shopId", "title", "status", "categoryId", "createdAt", "updatedAt"}
    ),
    "ProductSku": frozenset(
        {"productId", "status", "barcode", "price", "currency", "updatedAt"}
    ),
    "Category": frozenset(
        {"parentCategoryId", "name", "status", "updatedAt"}
    ),
    "Order": frozenset(
        {"shopId", "status", "totalAmount", "currency", "createdAt", "updatedAt"}
    ),
    "OrderLine": frozenset(
        {"orderId", "skuId", "quantity", "unitPrice", "lineAmount", "currency", "updatedAt"}
    ),
    "Shipment": frozenset(
        {"orderId", "status", "carrier", "trackingNo", "shippedAt", "updatedAt"}
    ),
    # D1.5: CustomerLite 必填字段（不含 PII；frozen/02 §P08 隐私最小化映射）
    "CustomerLite": frozenset(
        {"memberLevel", "status", "createdAt", "updatedAt"}
    ),
    # D4: 4 个新 OT 必填字段（frozen/02 §P09~P12）
    "Weapp": frozenset({"appId", "name", "status", "updatedAt"}),
    "SystemConfig": frozenset({"siteId", "module", "key", "updatedAt"}),
    "ProductReview": frozenset({"productId", "memberId", "score", "updatedAt"}),
    "Payment": frozenset({"orderId", "outTradeNo", "payStatus", "updatedAt"}),
}

_AMOUNT_PROPERTIES = frozenset({"price", "totalAmount", "unitPrice", "lineAmount"})


class EcomConsistencyError(Exception):
    """Stable internal error used at the W2/W3 integration boundary."""

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


StorageIdentity = ExternalIdentityKey


def _identity_scope(identity: ExternalIdentityKey) -> tuple[str, str, str, str]:
    return (
        identity.org_id,
        identity.workspace_id,
        identity.platform,
        identity.shop_or_marketplace_id,
    )


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("source_updated_at must be timezone-aware")
    return value.astimezone(timezone.utc)


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _jsonable(value.model_dump(mode="python"))
    if isinstance(value, datetime):
        return _aware_utc(value).isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def deterministic_hash(value: Any) -> str:
    payload = json.dumps(
        _jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CoreObjectRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    identity: ExternalIdentityKey
    object_type: str
    source_updated_at: datetime
    source_timezone: str = Field(min_length=1)
    status: ForwardEnumValue
    is_deleted: bool = False
    schema_version: int = Field(default=1, ge=1)
    properties: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_public_property_contracts(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        properties = dict(data.get("properties") or {})
        for field_name in _AMOUNT_PROPERTIES & properties.keys():
            if "currency" not in properties:
                continue
            money_input: dict[str, Any] = {
                "amount": properties[field_name],
                "currency": properties.get("currency"),
            }
            if "currencyScale" in properties:
                money_input["scale"] = properties["currencyScale"]
            money = Money.model_validate(money_input)
            properties[field_name] = money.model_dump(mode="json")["amount"]
            properties["currency"] = money.currency
            properties["currencyScale"] = money.scale
        for field_name in tuple(properties):
            if field_name.endswith("At") and not field_name.endswith("SourceTimezone"):
                instant = ZonedInstant.parse(properties[field_name])
                source_timezone_field = f"{field_name}SourceTimezone"
                existing_source_timezone = properties.get(source_timezone_field)
                properties[field_name] = instant.canonical_utc()
                if (
                    str(value.get("properties", {}).get(field_name, "")).strip()
                    == instant.canonical_utc()
                    and isinstance(existing_source_timezone, str)
                    and re.fullmatch(r"Z|[+-]\d{4}", existing_source_timezone)
                ):
                    properties[source_timezone_field] = existing_source_timezone
                else:
                    properties[source_timezone_field] = instant.source_timezone
        data["properties"] = properties
        return data

    @field_validator("source_updated_at")
    @classmethod
    def validate_source_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_core_shape(self) -> "CoreObjectRecord":
        if self.object_type not in CORE_OBJECT_TYPES:
            raise ValueError(f"unsupported core object type: {self.object_type}")
        if self.status.unknown and not self.status.raw_status.strip():
            raise ValueError("unknown canonical status requires raw_status")
        if not self.is_deleted:
            missing = sorted(REQUIRED_PROPERTIES[self.object_type] - self.properties.keys())
            if missing:
                raise ValueError(f"missing required properties for {self.object_type}: {missing}")
        return self

    def payload_hash(self) -> str:
        return deterministic_hash(
            {
                "identity": self.identity,
                "objectType": self.object_type,
                "sourceUpdatedAt": self.source_updated_at,
                "sourceTimezone": self.source_timezone,
                "status": self.status,
                "isDeleted": self.is_deleted,
                "schemaVersion": self.schema_version,
                "properties": self.properties,
            }
        )

    def cursor_key(self) -> tuple[datetime, str]:
        return self.source_updated_at, self.identity.external_id


class CoreLinkRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    link_type: str
    source_type: str
    source: ExternalIdentityKey
    target_type: str
    target: ExternalIdentityKey
    source_updated_at: datetime
    cursor_external_id: str = Field(min_length=1)
    is_deleted: bool = False
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_updated_at")
    @classmethod
    def validate_source_time(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @field_validator("cursor_external_id")
    @classmethod
    def validate_cursor_external_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("cursor_external_id must not be empty")
        return cleaned

    @model_validator(mode="after")
    def validate_link(self) -> "CoreLinkRecord":
        expected = CORE_LINK_TYPES.get(self.link_type)
        if expected is None:
            raise ValueError(f"unsupported core link type: {self.link_type}")
        if expected != (self.source_type, self.target_type):
            raise ValueError(
                f"{self.link_type} requires {expected[0]} -> {expected[1]}"
            )
        if _identity_scope(self.source) != _identity_scope(self.target):
            raise ValueError("cross-tenant links are forbidden")
        return self

    def payload_hash(self) -> str:
        return deterministic_hash(
            self.model_dump(mode="python", exclude={"cursor_external_id"})
        )

    def cursor_key(self) -> tuple[datetime, str]:
        return self.source_updated_at, self.cursor_external_id


class SyncScope(BaseModel):
    model_config = ConfigDict(frozen=True)

    org_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    shop_or_marketplace_id: str = Field(min_length=1)
    stream: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_scope(self) -> "SyncScope":
        for name in (
            "org_id",
            "workspace_id",
            "platform",
            "shop_or_marketplace_id",
            "stream",
        ):
            if getattr(self, name) != getattr(self, name).strip():
                raise ValueError(f"{name} must not contain surrounding whitespace")
        if self.platform != self.platform.lower():
            raise ValueError("platform must already be normalized by public_contracts")
        return self

    def identity_scope(self) -> tuple[str, str, str, str]:
        return (
            self.org_id,
            self.workspace_id,
            self.platform,
            self.shop_or_marketplace_id,
        )

    def key(self) -> tuple[str, str, str, str, str]:
        return (*self.identity_scope(), self.stream)


CheckpointPosition = StableCursor


class BatchCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    scope: SyncScope
    idempotency_key: str = Field(min_length=1)
    expected_checkpoint_version: int = Field(ge=0)
    next_checkpoint: CheckpointPosition
    objects: list[CoreObjectRecord] = Field(default_factory=list)
    links: list[CoreLinkRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_batch_scope(self) -> "BatchCommand":
        expected = self.scope.identity_scope()
        for record in self.objects:
            if _identity_scope(record.identity) != expected:
                raise ValueError("object identity is outside the batch scope")
        for link in self.links:
            if _identity_scope(link.source) != expected or _identity_scope(link.target) != expected:
                raise ValueError("link identity is outside the batch scope")
        batch_cursors = [record.cursor_key() for record in self.objects]
        batch_cursors.extend(link.cursor_key() for link in self.links)
        if not batch_cursors:
            raise ValueError("batch must contain at least one object or link")
        if self.next_checkpoint.sort_key() < max(batch_cursors):
            raise ValueError("next checkpoint is behind the batch data")
        return self

    def max_data_cursor(self) -> tuple[datetime, str]:
        return max(
            [record.cursor_key() for record in self.objects]
            + [link.cursor_key() for link in self.links]
        )

    def request_hash(self) -> str:
        return deterministic_hash(
            {
                "scope": self.scope,
                "expectedCheckpointVersion": self.expected_checkpoint_version,
                "nextCheckpoint": self.next_checkpoint,
                "objects": self.ordered_objects(),
                "links": self.ordered_links(),
            }
        )

    def ordered_objects(self) -> list[CoreObjectRecord]:
        return sorted(
            self.objects,
            key=lambda record: (*record.cursor_key(), record.object_type),
        )

    def ordered_links(self) -> list[CoreLinkRecord]:
        return sorted(
            self.links,
            key=lambda link: (
                *link.cursor_key(),
                link.link_type,
                link.source.external_id,
                link.target.external_id,
            ),
        )


class BatchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    replayed: bool = False
    objects_written: int = 0
    objects_ignored: int = 0
    objects_tombstoned: int = 0
    links_written: int = 0
    links_ignored: int = 0
    links_tombstoned: int = 0
    checkpoint_version: int
    checkpoint: CheckpointPosition


class DerivedMetricCommand(BaseModel):
    """O1 §5.2.10 内部派生指标 CAS 命令。"""

    model_config = ConfigDict(frozen=True)

    identity: ExternalIdentityKey
    object_type: str
    stream: str = Field(min_length=1)
    expected_derived_revision: int = Field(ge=0)
    input_revision: int = Field(ge=0)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    calculator_version: str = Field(min_length=1)
    derived_props: dict[str, Any]
    computed_at: datetime
    idempotency_key: str = Field(min_length=1)
    actor: str = Field(min_length=1)

    @field_validator("computed_at")
    @classmethod
    def validate_computed_at(cls, value: datetime) -> datetime:
        return _aware_utc(value)

    @model_validator(mode="after")
    def validate_derived_contract(self) -> "DerivedMetricCommand":
        allowed = DERIVED_PROPERTIES.get(self.object_type)
        if allowed is None:
            raise ValueError(f"unsupported derived object type: {self.object_type}")
        unknown = set(self.derived_props) - allowed
        if unknown:
            raise ValueError(f"unsupported derived properties: {sorted(unknown)}")
        if not self.derived_props:
            raise ValueError("derived_props must not be empty")
        return self

    def request_hash(self) -> str:
        return deterministic_hash(
            {
                "identity": self.identity,
                "objectType": self.object_type,
                "stream": self.stream,
                "expectedDerivedRevision": self.expected_derived_revision,
                "inputRevision": self.input_revision,
                "inputHash": self.input_hash,
                "calculatorVersion": self.calculator_version,
                "derivedProps": self.derived_props,
                "computedAt": self.computed_at,
                "actor": self.actor,
            }
        )


class DerivedMetricResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    updated: bool
    replayed: bool = False
    resulting_revision: int = Field(ge=0)
    input_revision: int = Field(ge=0)
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


def stable_incremental_window(
    records: Iterable[CoreObjectRecord],
    *,
    checkpoint: CheckpointPosition | None,
    lookback_seconds: int,
) -> list[CoreObjectRecord]:
    """Return a deterministic read window; persistence performs final dedupe."""

    if lookback_seconds < 0:
        raise ValueError("lookback_seconds must be non-negative")
    ordered = sorted(records, key=lambda record: record.cursor_key())
    if checkpoint is None:
        return ordered
    lower_bound = checkpoint.source_updated_at_utc - timedelta(seconds=lookback_seconds)
    return [record for record in ordered if record.source_updated_at >= lower_bound]
