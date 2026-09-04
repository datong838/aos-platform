"""Strict read-only contracts for content-campaign business inputs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext


CONTENT_CAMPAIGN_INPUTS_SCHEMA_VERSION = (
    "aos.ecommerce-workshop.content-campaign-inputs/v1"
)


class ContentCampaignInputRef(AipContractModel):
    resource_type: Literal[
        "Product", "ProductSku", "CampaignRevision", "CalendarEntryRevision"
    ]
    resource_id: str = Field(min_length=1, max_length=300)
    revision: int | None = Field(default=None, ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    authority: Literal["ecom_object", "content_campaign_authority"]


class ContentCampaignProductInput(AipContractModel):
    product_ref: ContentCampaignInputRef
    title: str = Field(min_length=1, max_length=500)
    price: str | None = Field(default=None, max_length=80)
    available_stock: int | None = Field(default=None, ge=0)
    business_status: str | None = Field(default=None, max_length=80)
    source_updated_at: datetime

    @field_validator("source_updated_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("product source time requires timezone")
        return value


class ContentCampaignInventoryInput(AipContractModel):
    sku_ref: ContentCampaignInputRef
    product_ref: ContentCampaignInputRef | None = None
    stock: int | None = Field(default=None, ge=0)
    stock_alarm: int | None = Field(default=None, ge=0)
    stock_health: Literal["low", "watch", "ok"] | None = None
    source_updated_at: datetime

    @field_validator("source_updated_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("inventory source time requires timezone")
        return value


class ContentCampaignPlanInput(AipContractModel):
    plan_ref: ContentCampaignInputRef
    lifecycle: str = Field(min_length=1, max_length=80)
    channel_ids: list[str] = Field(max_length=20)
    local_start: str | None = Field(default=None, max_length=40)
    local_end: str | None = Field(default=None, max_length=40)
    source_updated_at: datetime

    @field_validator("source_updated_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("plan source time requires timezone")
        return value


class ContentCampaignInputLedger(AipContractModel):
    products: int = Field(ge=0, le=100)
    inventory: int = Field(ge=0, le=100)
    plans: int = Field(ge=0, le=200)
    unmatched_inventory: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def _bounded(self) -> "ContentCampaignInputLedger":
        if self.unmatched_inventory > self.inventory:
            raise ValueError("unmatchedInventory cannot exceed inventory")
        return self


class WorkshopContentCampaignInputsEnvelope(AipContractModel):
    schema_version: Literal[CONTENT_CAMPAIGN_INPUTS_SCHEMA_VERSION] = (
        CONTENT_CAMPAIGN_INPUTS_SCHEMA_VERSION
    )
    tenant: TenantContext
    evaluated_at: datetime
    data_cutoff: datetime
    status: Literal["ready", "partial", "blocked"]
    products: list[ContentCampaignProductInput] = Field(max_length=100)
    inventory: list[ContentCampaignInventoryInput] = Field(max_length=100)
    plans: list[ContentCampaignPlanInput] = Field(max_length=200)
    ledger: ContentCampaignInputLedger
    unavailable_groups: list[Literal["products", "inventory", "plans"]] = Field(
        max_length=3
    )

    @field_validator("evaluated_at", "data_cutoff")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("content-campaign input times require timezone")
        return value

    @model_validator(mode="after")
    def _reconcile(self) -> "WorkshopContentCampaignInputsEnvelope":
        if self.ledger.products != len(self.products):
            raise ValueError("product ledger drift")
        if self.ledger.inventory != len(self.inventory):
            raise ValueError("inventory ledger drift")
        if self.ledger.plans != len(self.plans):
            raise ValueError("plan ledger drift")
        expected = "blocked" if len(self.unavailable_groups) == 3 else (
            "partial" if self.unavailable_groups else "ready"
        )
        if self.status != expected:
            raise ValueError("input status drift")
        return self


__all__ = [
    "CONTENT_CAMPAIGN_INPUTS_SCHEMA_VERSION",
    "ContentCampaignInputLedger",
    "ContentCampaignInputRef",
    "ContentCampaignInventoryInput",
    "ContentCampaignPlanInput",
    "ContentCampaignProductInput",
    "WorkshopContentCampaignInputsEnvelope",
]
