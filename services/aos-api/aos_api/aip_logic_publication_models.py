"""Strict contracts for immutable, governed AIP Logic publications."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aos_api.aip_logic_graph_models import LogicGraphSnapshot

MAX_SAFE_INTEGER = 9_007_199_254_740_991


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PublishLogicGraphRequest(_StrictModel):
    expected_revision: int = Field(ge=1, le=MAX_SAFE_INTEGER)
    expected_graph_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    eval_suite_id: str = Field(min_length=1, max_length=160)
    eval_report_id: str = Field(min_length=1, max_length=160)
    idempotency_key: str = Field(min_length=1, max_length=160)

    @field_validator("eval_suite_id", "eval_report_id", "idempotency_key")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class LogicEvalEvidence(_StrictModel):
    """Immutable Evals result returned by the injected durable evidence provider."""

    suite_id: str = Field(min_length=1, max_length=160)
    report_id: str = Field(min_length=1, max_length=160)
    target_type: Literal["logic_graph"] = "logic_graph"
    target_id: str = Field(min_length=1, max_length=160)
    target_revision: int = Field(ge=1, le=MAX_SAFE_INTEGER)
    target_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    gate_passed: bool
    pass_rate: float = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)
    passed: int = Field(ge=0, le=MAX_SAFE_INTEGER)
    failed: int = Field(ge=0, le=MAX_SAFE_INTEGER)
    total: int = Field(ge=1, le=MAX_SAFE_INTEGER)
    run_at: datetime
    expires_at: datetime | None = None

    @field_validator("suite_id", "report_id", "target_id")
    @classmethod
    def _evidence_id_non_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @model_validator(mode="after")
    def _truthful_counts_and_gate(self) -> LogicEvalEvidence:
        if self.passed + self.failed != self.total:
            raise ValueError("passed + failed must equal total")
        if self.expires_at is not None and self.expires_at <= self.run_at:
            raise ValueError("expires_at must be after run_at")
        return self


class LogicPublicationGateSummary(_StrictModel):
    gate_passed: Literal[True] = True
    pass_rate: float = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)
    passed: int = Field(ge=0, le=MAX_SAFE_INTEGER)
    failed: int = Field(ge=0, le=MAX_SAFE_INTEGER)
    total: int = Field(ge=1, le=MAX_SAFE_INTEGER)
    run_at: datetime

    @model_validator(mode="after")
    def _truthful_gate(self) -> LogicPublicationGateSummary:
        if self.passed + self.failed != self.total:
            raise ValueError("passed + failed must equal total")
        if self.pass_rate < self.threshold:
            raise ValueError("passed gate requires pass_rate >= threshold")
        return self


class LogicPublication(_StrictModel):
    publication_id: str = Field(min_length=1, max_length=160)
    graph_id: str = Field(min_length=1, max_length=160)
    graph_revision: int = Field(ge=1, le=MAX_SAFE_INTEGER)
    graph_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    graph_snapshot: LogicGraphSnapshot
    dry_run_id: str = Field(min_length=1, max_length=160)
    eval_suite_id: str = Field(min_length=1, max_length=160)
    eval_report_id: str = Field(min_length=1, max_length=160)
    eval_gate: LogicPublicationGateSummary
    actor: str = Field(min_length=1, max_length=320)
    created_at: datetime

    @model_validator(mode="after")
    def _snapshot_matches_publication(self) -> LogicPublication:
        if (
            self.graph_snapshot.id != self.graph_id
            or self.graph_snapshot.revision != self.graph_revision
            or self.graph_snapshot.graph_hash != self.graph_hash
        ):
            raise ValueError("publication graph snapshot does not match its target")
        return self


class LogicPublicationListResponse(_StrictModel):
    items: list[LogicPublication] = Field(default_factory=list)
    count: int = Field(ge=0)

    @model_validator(mode="after")
    def _count_matches_items(self) -> LogicPublicationListResponse:
        if self.count != len(self.items):
            raise ValueError("count must equal the number of items")
        return self
