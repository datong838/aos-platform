"""Strict AIP-8 analyst query contracts.

These contracts describe governed reads only.  Tenant scope always comes from
the authenticated Principal and is therefore response context, never request
authority.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import Field, TypeAdapter, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, ResourceRef, TenantContext


class AnalystQueryKind(StrEnum):
    SEMANTIC = "semantic"
    KNOWLEDGE = "knowledge"
    METRIC = "metric"


class AnalystQueryStatus(StrEnum):
    COMPLETE = "complete"
    EMPTY = "empty"
    DEGRADED = "degraded"
    PARTIAL = "partial"
    BLOCKED = "blocked"


class QueryJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class QueryJobEventKind(StrEnum):
    CREATED = "created"
    STARTED = "started"
    RESULT_RECORDED = "result_recorded"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    FAILED = "failed"
    RECONCILED = "reconciled"


class QueryBlocker(AipContractModel):
    code: str = Field(min_length=1, max_length=160)
    message: str = Field(min_length=1, max_length=500)
    dependency_ref: ResourceRef | None = None
    retryable: bool = False


class QuerySourceRef(AipContractModel):
    ref: ResourceRef
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    cutoff_at: datetime
    freshness: Literal["fresh", "stale", "unknown"]
    markings: list[str] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def _exact_revision(self) -> "QuerySourceRef":
        if not self.ref.revision:
            raise ValueError("query source refs require an exact revision")
        return self


class QueryColumn(AipContractModel):
    key: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=240)
    value_type: Literal["string", "number", "boolean", "datetime", "object_ref"]
    marking: str | None = Field(default=None, min_length=1, max_length=120)


class QueryRow(AipContractModel):
    row_id: str = Field(min_length=1, max_length=240)
    values: dict[str, Any]


class QueryFilter(AipContractModel):
    field: str = Field(min_length=1, max_length=160)
    operator: Literal["eq", "neq", "lt", "lte", "gt", "gte", "in", "contains"]
    value: Any


class SemanticQueryRequest(AipContractModel):
    kind: Literal[AnalystQueryKind.SEMANTIC] = AnalystQueryKind.SEMANTIC
    object_type: str = Field(min_length=1, max_length=160)
    filters: list[QueryFilter] = Field(default_factory=list, max_length=10)
    selection_refs: list[ResourceRef] = Field(default_factory=list, max_length=100)
    page_size: int = Field(default=50, ge=1, le=200)
    cutoff_at: datetime


class KnowledgeQueryRequest(AipContractModel):
    kind: Literal[AnalystQueryKind.KNOWLEDGE] = AnalystQueryKind.KNOWLEDGE
    query: str = Field(min_length=2, max_length=500)
    task_ref: ResourceRef
    skill_ref: ResourceRef
    selection_refs: list[ResourceRef] = Field(default_factory=list, max_length=100)
    markings: list[str] = Field(min_length=1, max_length=32)
    max_tokens: int = Field(default=2048, ge=64, le=32768)
    cutoff_at: datetime

    @field_validator("query")
    @classmethod
    def _clean_query(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("knowledge query is too short")
        return cleaned


class MetricQueryRequest(AipContractModel):
    kind: Literal[AnalystQueryKind.METRIC] = AnalystQueryKind.METRIC
    metric_ref: ResourceRef
    dimensions: list[str] = Field(default_factory=list, max_length=8)
    filters: list[QueryFilter] = Field(default_factory=list, max_length=10)
    selection_refs: list[ResourceRef] = Field(default_factory=list, max_length=100)
    window_start: datetime
    window_end: datetime
    cutoff_at: datetime

    @model_validator(mode="after")
    def _valid_window(self) -> "MetricQueryRequest":
        if self.window_start >= self.window_end:
            raise ValueError("metric windowStart must be before windowEnd")
        if self.window_end > self.cutoff_at:
            raise ValueError("metric windowEnd must not exceed cutoffAt")
        return self


AnalystQueryRequest = Annotated[
    SemanticQueryRequest | KnowledgeQueryRequest | MetricQueryRequest,
    Field(discriminator="kind"),
]
ANALYST_QUERY_ADAPTER = TypeAdapter(AnalystQueryRequest)


class QueryResultRevision(AipContractModel):
    tenant: TenantContext
    query_id: str = Field(min_length=1, max_length=240)
    revision: int = Field(ge=1)
    kind: AnalystQueryKind
    status: AnalystQueryStatus
    columns: list[QueryColumn] = Field(default_factory=list, max_length=256)
    rows: list[QueryRow] = Field(default_factory=list, max_length=1000)
    source_refs: list[QuerySourceRef] = Field(default_factory=list, max_length=100)
    lineage_refs: list[ResourceRef] = Field(default_factory=list, max_length=100)
    blockers: list[QueryBlocker] = Field(default_factory=list, max_length=100)
    uncertainties: list[str] = Field(default_factory=list, max_length=100)
    cutoff_at: datetime
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime

    @model_validator(mode="after")
    def _honest_state(self) -> "QueryResultRevision":
        if self.status == AnalystQueryStatus.BLOCKED:
            if self.rows or self.columns or self.source_refs or not self.blockers:
                raise ValueError("blocked query results contain blockers only")
        elif self.status == AnalystQueryStatus.EMPTY:
            if self.rows or self.blockers or not self.source_refs:
                raise ValueError("empty query results require sources and no rows/blockers")
        else:
            if not self.source_refs or self.blockers:
                raise ValueError("non-blocked query results require sources and no blockers")
        if self.status == AnalystQueryStatus.COMPLETE and not self.rows:
            raise ValueError("complete query results require rows")
        if self.status in {AnalystQueryStatus.DEGRADED, AnalystQueryStatus.PARTIAL}:
            if not self.uncertainties:
                raise ValueError("degraded/partial query results require uncertainties")
        if self.cutoff_at > self.created_at:
            raise ValueError("query result cutoffAt must not exceed createdAt")

        column_keys = [column.key for column in self.columns]
        row_ids = [row.row_id for row in self.rows]
        if len(column_keys) != len(set(column_keys)):
            raise ValueError("query result columns must be unique")
        if len(row_ids) != len(set(row_ids)):
            raise ValueError("query result rowIds must be unique")
        if self.rows and not self.columns:
            raise ValueError("query result rows require columns")
        allowed_values = set(column_keys)
        if any(not set(row.values).issubset(allowed_values) for row in self.rows):
            raise ValueError("query row values must match declared columns")
        if any(source.cutoff_at > self.cutoff_at for source in self.source_refs):
            raise ValueError("query source cutoffAt must not exceed result cutoffAt")
        return self


class CreateQueryJobRequest(AipContractModel):
    query: AnalystQueryRequest
    deadline_at: datetime

    @model_validator(mode="after")
    def _deadline_after_cutoff(self) -> "CreateQueryJobRequest":
        if self.deadline_at <= self.query.cutoff_at:
            raise ValueError("deadlineAt must be after query cutoffAt")
        return self


class QueryJobCommand(AipContractModel):
    expected_sequence: int = Field(ge=1)
    reason_code: str = Field(min_length=1, max_length=160)


class RecordQueryResultRequest(AipContractModel):
    expected_sequence: int = Field(ge=1)
    result: QueryResultRevision


class QueryJobSnapshot(AipContractModel):
    tenant: TenantContext
    query_id: str = Field(min_length=1, max_length=240)
    query: AnalystQueryRequest
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: QueryJobStatus
    latest_sequence: int = Field(ge=1)
    latest_event_kind: QueryJobEventKind
    latest_reason_code: str | None = None
    deadline_at: datetime
    created_by: str = Field(min_length=1, max_length=240)
    created_at: datetime
    latest_result: QueryResultRevision | None = None


__all__ = [
    "ANALYST_QUERY_ADAPTER",
    "AnalystQueryKind",
    "AnalystQueryRequest",
    "AnalystQueryStatus",
    "CreateQueryJobRequest",
    "KnowledgeQueryRequest",
    "MetricQueryRequest",
    "QueryBlocker",
    "QueryColumn",
    "QueryFilter",
    "QueryResultRevision",
    "QueryJobCommand",
    "QueryJobEventKind",
    "QueryJobSnapshot",
    "QueryJobStatus",
    "RecordQueryResultRequest",
    "QueryRow",
    "QuerySourceRef",
    "SemanticQueryRequest",
]
