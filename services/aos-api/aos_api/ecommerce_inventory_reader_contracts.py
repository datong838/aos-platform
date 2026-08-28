"""Strict internal contracts for the D0 ProductSku inventory reader."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext


INVENTORY_READER_SCHEMA_VERSION = "aos.ecommerce.inventory-reader/v1"


class InventoryHealth(StrEnum):
    LOW = "low"
    WATCH = "watch"
    OK = "ok"


class InventoryObjectRevision(AipContractModel):
    resource_type: Literal["ProductSku"] = "ProductSku"
    resource_id: str = Field(min_length=1, max_length=300)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    authority: Literal["ecom_object"] = "ecom_object"


class InventoryReadItem(AipContractModel):
    object_id: str = Field(min_length=1, max_length=300)
    stock: int | None = Field(default=None, ge=0)
    stock_alarm: int | None = Field(default=None, ge=0)
    stock_health: InventoryHealth | None = None
    source_updated_at: datetime
    revision: InventoryObjectRevision

    @field_validator("source_updated_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Inventory sourceUpdatedAt requires a timezone")
        return value

    @model_validator(mode="after")
    def _identity_matches_ref(self) -> InventoryReadItem:
        if self.revision.resource_id != self.object_id:
            raise ValueError("Inventory objectId must match its exact revision ref")
        return self


class InventoryReadPage(AipContractModel):
    limit: int = Field(ge=1, le=100)
    count: int = Field(ge=0, le=100)
    unknown_count: int = Field(default=0, ge=0, le=100)
    has_more: bool

    @model_validator(mode="after")
    def _unknown_is_bounded(self) -> InventoryReadPage:
        if self.unknown_count > self.count:
            raise ValueError("Inventory unknownCount cannot exceed count")
        return self


class InventoryReadEnvelope(AipContractModel):
    schema_version: Literal[INVENTORY_READER_SCHEMA_VERSION] = (
        INVENTORY_READER_SCHEMA_VERSION
    )
    tenant: TenantContext
    cutoff: datetime
    items: list[InventoryReadItem] = Field(max_length=100)
    page: InventoryReadPage

    @field_validator("cutoff")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Inventory cutoff requires a timezone")
        return value

    @model_validator(mode="after")
    def _canonical_page(self) -> InventoryReadEnvelope:
        if self.page.count != len(self.items):
            raise ValueError("Inventory page count must equal item count")
        identities = [item.object_id for item in self.items]
        if len(identities) != len(set(identities)):
            raise ValueError("Inventory object identities must be unique")
        return self


__all__ = [
    "INVENTORY_READER_SCHEMA_VERSION",
    "InventoryHealth",
    "InventoryObjectRevision",
    "InventoryReadEnvelope",
    "InventoryReadItem",
    "InventoryReadPage",
]
