"""Strict read-only contracts for the ecommerce Operations view."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext


OPERATIONS_SCHEMA_VERSION = "aos.ecommerce-workshop.operations-view/v1"


class OperationsReadiness(StrEnum):
    DEGRADED = "degraded"


class OperationsSliceId(StrEnum):
    ORDERS = "orders"
    ORDER_LINES = "orderLines"
    INVENTORY = "inventory"
    SHIPMENTS = "shipments"
    PAYMENTS = "payments"
    AFTERSALE_EVENTS = "aftersaleEvents"
    OPERATION_CASES = "operationCases"


class OperationsSliceStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


class OperationsAuthorityRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    receipt_id: str = Field(min_length=1, max_length=200)


class OperationsBlocker(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    dependency: str = Field(min_length=1, max_length=160)
    required_action: str = Field(min_length=1, max_length=500)


class OperationsCountLedger(AipContractModel):
    source_total: int = Field(ge=0)
    attached: int = Field(ge=0)
    unmatched: int = Field(ge=0)
    conflicted: int = Field(ge=0)

    @model_validator(mode="after")
    def _counts_reconcile(self) -> OperationsCountLedger:
        if self.source_total != self.attached + self.unmatched + self.conflicted:
            raise ValueError("sourceTotal must equal attached + unmatched + conflicted")
        return self


class OperationsSliceReadiness(AipContractModel):
    slice_id: OperationsSliceId
    status: OperationsSliceStatus
    data_cutoff: datetime
    authority_refs: list[OperationsAuthorityRef] = Field(max_length=20)
    blockers: list[OperationsBlocker] = Field(max_length=20)
    count_ledger: OperationsCountLedger

    @field_validator("data_cutoff")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Operations timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _status_matches_evidence(self) -> OperationsSliceReadiness:
        if self.status is OperationsSliceStatus.READY:
            if not self.authority_refs or self.blockers:
                raise ValueError("ready slices require authorityRefs and no blockers")
        elif not self.blockers:
            raise ValueError("blocked slices require at least one blocker")
        return self


class OperationsPageInfo(AipContractModel):
    limit: int = Field(ge=1, le=100)
    count: int = Field(ge=0, le=100)
    has_more: bool
    next_cursor: str | None = Field(default=None, max_length=4096)

    @model_validator(mode="after")
    def _cursor_matches_more(self) -> OperationsPageInfo:
        if self.has_more != (self.next_cursor is not None):
            raise ValueError("hasMore and nextCursor must agree")
        return self


class WorkshopOperationsViewEnvelope(AipContractModel):
    schema_version: Literal[OPERATIONS_SCHEMA_VERSION] = OPERATIONS_SCHEMA_VERSION
    tenant: TenantContext
    evaluated_at: datetime
    data_cutoff: datetime
    readiness: Literal[OperationsReadiness.DEGRADED] = OperationsReadiness.DEGRADED
    slices: list[OperationsSliceReadiness] = Field(min_length=7, max_length=7)
    page: OperationsPageInfo

    @field_validator("evaluated_at", "data_cutoff")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Operations timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _canonical_shape(self) -> WorkshopOperationsViewEnvelope:
        if [item.slice_id for item in self.slices] != list(OperationsSliceId):
            raise ValueError("Operations slices must use canonical order and identity")
        if self.page.count != 0:
            raise ValueError("W2-01A shell cannot claim business rows")
        if self.page.has_more or self.page.next_cursor is not None:
            raise ValueError("W2-01A shell cannot expose a synthetic cursor")
        return self


__all__ = [
    "OPERATIONS_SCHEMA_VERSION",
    "OperationsAuthorityRef",
    "OperationsBlocker",
    "OperationsCountLedger",
    "OperationsPageInfo",
    "OperationsReadiness",
    "OperationsSliceId",
    "OperationsSliceReadiness",
    "OperationsSliceStatus",
    "WorkshopOperationsViewEnvelope",
]
