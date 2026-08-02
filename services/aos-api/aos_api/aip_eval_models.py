"""Strict persisted evidence contracts for tenant-scoped Logic Evals."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aos_api.evals_engine import CaseResult

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LogicGraphEvalTarget(_StrictModel):
    target_type: Literal["logic_graph"]
    target_id: str = Field(min_length=1, max_length=160)
    target_revision: int = Field(ge=1)
    target_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class EvalReportEvidence(LogicGraphEvalTarget):
    """Immutable report shape persisted by :class:`EvalEvidenceStore`.

    The legacy report fields remain unchanged so the existing Evals page can
    render this richer evidence without synthesising a second contract.
    """

    report_id: str = Field(
        default_factory=lambda: f"eval-report-{uuid.uuid4().hex}",
        min_length=1,
        max_length=160,
    )
    suite_id: str = Field(min_length=1, max_length=160)
    results: list[CaseResult] = Field(default_factory=list)
    pass_rate: float = Field(ge=0.0, le=1.0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    total: int = Field(ge=1)
    gate_passed: bool
    run_at: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def _consistent_counts(self) -> EvalReportEvidence:
        if not _SHA256_RE.fullmatch(self.target_hash):
            raise ValueError("target_hash must be a lowercase SHA-256 digest")
        if self.total != len(self.results):
            raise ValueError("total must equal result count")
        actual_passed = sum(1 for result in self.results if result.passed)
        if self.passed != actual_passed or self.failed != self.total - actual_passed:
            raise ValueError("passed/failed counts contradict results")
        expected_rate = round(actual_passed / self.total, 4)
        if self.pass_rate != expected_rate:
            raise ValueError("pass_rate contradicts results")
        return self


class EvalGateEvidence(LogicGraphEvalTarget):
    report_id: str = Field(min_length=1, max_length=160)
    suite_id: str = Field(min_length=1, max_length=160)
    gate_passed: bool
    pass_rate: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    total: int = Field(ge=1)
    run_at: str = Field(min_length=1, max_length=80)


class LogicEvalEvidence(LogicGraphEvalTarget):
    """Minimal durable evidence consumed inside the publication transaction."""

    suite_id: str = Field(min_length=1, max_length=160)
    report_id: str = Field(min_length=1, max_length=160)
    gate_passed: bool
    pass_rate: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    total: int = Field(ge=1)
    run_at: datetime
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def _is_publishable(self) -> LogicEvalEvidence:
        if self.total != self.passed + self.failed:
            raise ValueError("eval evidence counts are inconsistent")
        if not self.gate_passed or self.pass_rate < self.threshold:
            raise ValueError("eval evidence did not pass its persisted threshold")
        return self


def gate_from_report(
    report: EvalReportEvidence, *, threshold: float
) -> EvalGateEvidence:
    return EvalGateEvidence(
        report_id=report.report_id,
        suite_id=report.suite_id,
        target_type=report.target_type,
        target_id=report.target_id,
        target_revision=report.target_revision,
        target_hash=report.target_hash,
        gate_passed=report.gate_passed,
        pass_rate=report.pass_rate,
        threshold=threshold,
        passed=report.passed,
        failed=report.failed,
        total=report.total,
        run_at=report.run_at,
    )
