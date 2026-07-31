"""Platform-neutral core-7 ecommerce ontology and incremental contracts.

Public identity, money, time and enum parsing belong to ``public_contracts``.
This module only projects an already validated public identity into the
internal tenant-safe storage key used by the consistency store.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aos_api.public_contracts import (
    ExternalIdentityKey,
    ForwardEnumValue,
    Money,
    StableCursor,
)


CORE_OBJECT_TYPES = frozenset(
    {"Shop", "Product", "ProductSku", "Category", "Order", "OrderLine", "Shipment"}
)

CORE_LINK_TYPES: dict[str, tuple[str, str]] = {
    "Order.lines": ("Order", "OrderLine"),
    "OrderLine.ofSku": ("OrderLine", "ProductSku"),
    "ProductSku.ofProduct": ("ProductSku", "Product"),
    "Product.inCategory": ("Product", "Category"),
    "Shop.sellsProduct": ("Shop", "Product"),
    "Order.fulfilledBy": ("Order", "Shipment"),
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
        for field_name in _AMOUNT_PROPERTIES & self.properties.keys():
            Money.model_validate(
                {
                    "amount": self.properties[field_name],
                    "currency": self.properties.get("currency"),
                }
            )
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
            self.model_dump(mode="python", exclude={"idempotency_key"})
        )

    def ordered_objects(self) -> list[CoreObjectRecord]:
        return sorted(self.objects, key=lambda record: record.cursor_key())


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
