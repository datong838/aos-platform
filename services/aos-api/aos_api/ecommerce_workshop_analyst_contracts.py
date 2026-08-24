"""Strict read-only contracts for the ecommerce analyst aggregate view."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext

ANALYST_SCHEMA_VERSION = "aos.ecommerce-workshop.analyst-view/v1"


class AnalystViewId(StrEnum):
    OVERVIEW = "overview"
    DRIVERS = "drivers"
    DIAGNOSIS = "diagnosis"
    PLAN = "plan"
    EFFECTS = "effects"
    EVIDENCE = "evidence"
    QUALITY = "quality"


class AnalystReadinessAxis(StrEnum):
    METRIC_QUERY = "metric_query"
    MODEL = "model"
    EVAL = "eval"
    PLAN_MATERIALIZATION = "plan_materialization"
    PROFESSIONAL_HANDOFF = "professional_handoff"


class AnalystReadinessStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class AnalystExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    receipt_id: str = Field(min_length=1, max_length=200)


class AnalystBlocker(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    dependency: str = Field(min_length=1, max_length=180)
    required_action: str = Field(min_length=1, max_length=500)


class AnalystAxisReadiness(AipContractModel):
    axis: AnalystReadinessAxis
    status: AnalystReadinessStatus
    exact_ref: AnalystExactRef | None = None
    blockers: list[AnalystBlocker] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _honest_status(self) -> AnalystAxisReadiness:
        if self.status is AnalystReadinessStatus.READY and (self.exact_ref is None or self.blockers):
            raise ValueError("ready analyst axis requires exact ref and no blockers")
        if self.status in {AnalystReadinessStatus.BLOCKED, AnalystReadinessStatus.UNKNOWN} and (self.exact_ref is not None or not self.blockers):
            raise ValueError("blocked or unknown analyst axis requires blockers and no exact ref")
        if self.status is AnalystReadinessStatus.NOT_APPLICABLE and (self.exact_ref is not None or self.blockers):
            raise ValueError("not-applicable analyst axis cannot attach ref or blockers")
        return self


class AnalystMetricValue(AipContractModel):
    metric_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,119}$")
    status: Literal["ready", "unknown", "blocked", "conflict"]
    definition_ref: AnalystExactRef | None = None
    observation_ref: AnalystExactRef | None = None
    value: float | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=80)
    grain: str | None = Field(default=None, min_length=1, max_length=80)
    window: str | None = Field(default=None, min_length=1, max_length=120)
    timezone: str | None = Field(default=None, min_length=1, max_length=80)
    cohort_filter: str | None = Field(default=None, min_length=1, max_length=500)
    numerator: float | None = None
    denominator: float | None = None
    source_run_ref: AnalystExactRef | None = None
    quality_ref: AnalystExactRef | None = None
    reconciliation_ref: AnalystExactRef | None = None
    lineage_id: str | None = Field(default=None, min_length=1, max_length=200)
    blockers: list[AnalystBlocker] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _unknown_is_not_zero(self) -> AnalystMetricValue:
        numbers = [self.value, self.numerator, self.denominator]
        if any(item is not None and not isfinite(item) for item in numbers):
            raise ValueError("analyst metric numbers must be finite")
        required = [self.definition_ref, self.observation_ref, self.value, self.unit, self.grain, self.window, self.timezone, self.cohort_filter, self.numerator, self.denominator, self.source_run_ref, self.quality_ref, self.reconciliation_ref, self.lineage_id]
        if self.status == "ready":
            if any(item is None for item in required) or self.denominator is None or self.denominator <= 0 or self.blockers:
                raise ValueError("ready analyst metric requires complete exact semantics and positive denominator")
        elif any(item is not None for item in numbers) or not self.blockers:
            raise ValueError("non-ready analyst metric cannot expose a value and requires blockers")
        return self


class AnalystCountLedger(AipContractModel):
    denominator: int = Field(ge=0)
    ready: int = Field(ge=0)
    unknown: int = Field(ge=0)
    blocked: int = Field(ge=0)
    conflict: int = Field(ge=0)

    @model_validator(mode="after")
    def _conserves(self) -> AnalystCountLedger:
        if self.denominator != self.ready + self.unknown + self.blocked + self.conflict:
            raise ValueError("analyst metric ledger must conserve denominator")
        return self


class AnalystViewSlice(AipContractModel):
    view_id: AnalystViewId
    status: Literal["ready", "blocked"]
    resource_revision: int = Field(ge=1)
    data_cutoff: datetime
    readiness_axes: list[AnalystAxisReadiness] = Field(min_length=5, max_length=5)
    metrics: list[AnalystMetricValue] = Field(default_factory=list, max_length=100)
    authority_refs: list[AnalystExactRef] = Field(default_factory=list, max_length=100)
    blockers: list[AnalystBlocker] = Field(default_factory=list, max_length=20)
    count_ledger: AnalystCountLedger

    @field_validator("data_cutoff")
    @classmethod
    def _aware_cutoff(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("analyst cutoff requires timezone")
        return value

    @model_validator(mode="after")
    def _canonical_and_honest(self) -> AnalystViewSlice:
        if [item.axis for item in self.readiness_axes] != list(AnalystReadinessAxis):
            raise ValueError("analyst readiness axes require canonical order")
        identities = [(item.resource_type, item.resource_id, item.revision, item.content_hash, item.receipt_id) for item in self.authority_refs]
        if len(identities) != len(set(identities)):
            raise ValueError("analyst authority refs must be unique")
        counts = {status: sum(item.status == status for item in self.metrics) for status in ("ready", "unknown", "blocked", "conflict")}
        if self.count_ledger.denominator != len(self.metrics) or any(getattr(self.count_ledger, key) != value for key, value in counts.items()):
            raise ValueError("analyst metric ledger must equal metric partitions")
        axis_blocked = any(item.status in {AnalystReadinessStatus.BLOCKED, AnalystReadinessStatus.UNKNOWN} for item in self.readiness_axes)
        if self.status == "ready" and (self.blockers or axis_blocked):
            raise ValueError("ready analyst view cannot hide blocked axes")
        if self.status == "blocked" and not self.blockers:
            raise ValueError("blocked analyst view requires blockers")
        return self


class AnalystPageInfo(AipContractModel):
    limit: Literal[100] = 100
    count: int = Field(ge=0, le=700)
    has_more: Literal[False] = False
    next_cursor: None = None


class WorkshopAnalystViewEnvelope(AipContractModel):
    schema_version: Literal[ANALYST_SCHEMA_VERSION] = ANALYST_SCHEMA_VERSION
    tenant: TenantContext
    resource_revision: int = Field(ge=1)
    evaluated_at: datetime
    data_cutoff: datetime
    readiness: Literal["degraded"] = "degraded"
    views: list[AnalystViewSlice] = Field(min_length=7, max_length=7)
    page: AnalystPageInfo

    @field_validator("evaluated_at", "data_cutoff")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("analyst timestamps require timezone")
        return value

    @model_validator(mode="after")
    def _canonical_shape(self) -> WorkshopAnalystViewEnvelope:
        if [item.view_id for item in self.views] != list(AnalystViewId):
            raise ValueError("analyst views require canonical order")
        if any(item.data_cutoff != self.data_cutoff or item.resource_revision != self.resource_revision for item in self.views):
            raise ValueError("analyst views require one revision and cutoff")
        if self.page.count != sum(len(item.metrics) for item in self.views):
            raise ValueError("analyst page count must equal metrics")
        return self


__all__ = ["ANALYST_SCHEMA_VERSION", "AnalystAxisReadiness", "AnalystBlocker", "AnalystCountLedger", "AnalystExactRef", "AnalystMetricValue", "AnalystPageInfo", "AnalystReadinessAxis", "AnalystReadinessStatus", "AnalystViewId", "AnalystViewSlice", "WorkshopAnalystViewEnvelope"]
