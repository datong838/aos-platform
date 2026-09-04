"""Strict read contracts for the tenant-bound operation case workspace."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.ecommerce_operation_case_contracts import (
    ExactAuthorityRevisionRef,
    ExactOriginalRef,
    OperationCaseStatus,
)


OPERATION_CASE_WORKSPACE_SCHEMA_VERSION = (
    "aos.ecommerce-workshop.operation-case-workspace/v1"
)


class OperationCaseWorkspaceStatus(StrEnum):
    READY = "ready"
    PARTIAL = "partial"
    BLOCKED = "blocked"


class OperationCaseWorkspaceSourceId(StrEnum):
    ORDERS = "orders"
    INVENTORY = "inventory"
    SHIPMENTS = "shipments"
    AFTERSALE_EVENTS = "aftersaleEvents"
    PAYMENTS = "payments"
    OPERATION_CASES = "operationCases"


class OperationCaseWorkspaceSourceStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


class OperationCaseWorkspaceBlocker(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    required_action: str = Field(min_length=1, max_length=500)


class OperationCaseWorkspaceSource(AipContractModel):
    source_id: OperationCaseWorkspaceSourceId
    status: OperationCaseWorkspaceSourceStatus
    count: int = Field(ge=0)
    blocker: OperationCaseWorkspaceBlocker | None = None

    @model_validator(mode="after")
    def _status_matches_blocker(self) -> "OperationCaseWorkspaceSource":
        if self.status is OperationCaseWorkspaceSourceStatus.READY and self.blocker:
            raise ValueError("ready source cannot have blocker")
        if self.status is OperationCaseWorkspaceSourceStatus.BLOCKED and not self.blocker:
            raise ValueError("blocked source requires blocker")
        if self.status is OperationCaseWorkspaceSourceStatus.BLOCKED and self.count:
            raise ValueError("blocked source cannot claim a count")
        return self


class OperationCaseMemberLedger(AipContractModel):
    orders: int = Field(ge=0)
    order_lines: int = Field(ge=0)
    inventory: int = Field(ge=0)
    shipments: int = Field(ge=0)
    payments: int = Field(ge=0)
    aftersale_events: int = Field(ge=0)
    total: int = Field(ge=0)

    @model_validator(mode="after")
    def _reconciles(self) -> "OperationCaseMemberLedger":
        member_total = sum(
            (
                self.orders,
                self.order_lines,
                self.inventory,
                self.shipments,
                self.payments,
                self.aftersale_events,
            )
        )
        if self.total != member_total:
            raise ValueError("operation case member ledger must reconcile")
        return self


class OperationCaseWorkspaceCase(AipContractModel):
    case_ref: ExactAuthorityRevisionRef
    version: int = Field(ge=1)
    status: OperationCaseStatus
    priority: Literal["low", "normal", "high", "critical"]
    member_refs: list[ExactOriginalRef] = Field(max_length=250)
    member_ledger: OperationCaseMemberLedger

    @model_validator(mode="after")
    def _members_reconcile(self) -> "OperationCaseWorkspaceCase":
        if self.member_ledger.total != len(self.member_refs):
            raise ValueError("case member count must match exact refs")
        return self


class OperationCaseCandidateKind(StrEnum):
    INVENTORY_DATA_GAP = "inventory_data_gap"
    AFTERSALE_FOLLOWUP = "aftersale_followup"


class OperationCaseWorkspaceCandidate(AipContractModel):
    candidate_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    kind: OperationCaseCandidateKind
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=500)
    priority: Literal["normal", "high"]
    member_refs: list[ExactOriginalRef] = Field(min_length=1, max_length=20)
    external_effect_allowed: Literal[False] = False


class OperationCaseWorkspaceLedger(AipContractModel):
    source_total: int = Field(ge=0)
    assigned: int = Field(ge=0)
    unassigned: int = Field(ge=0)
    candidates: int = Field(ge=0)
    open_cases: int = Field(ge=0)
    paused_cases: int = Field(ge=0)
    closed_cases: int = Field(ge=0)

    @model_validator(mode="after")
    def _reconciles(self) -> "OperationCaseWorkspaceLedger":
        if self.source_total != self.assigned + self.unassigned:
            raise ValueError("workspace assignment ledger must reconcile")
        if self.candidates > self.unassigned:
            raise ValueError("workspace candidates cannot exceed unassigned facts")
        return self


class OperationCaseWorkspaceEnvelope(AipContractModel):
    schema_version: Literal[OPERATION_CASE_WORKSPACE_SCHEMA_VERSION] = (
        OPERATION_CASE_WORKSPACE_SCHEMA_VERSION
    )
    tenant: TenantContext
    status: OperationCaseWorkspaceStatus
    evaluated_at: datetime
    data_cutoff: datetime
    sources: list[OperationCaseWorkspaceSource] = Field(min_length=6, max_length=6)
    cases: list[OperationCaseWorkspaceCase] = Field(max_length=50)
    candidates: list[OperationCaseWorkspaceCandidate] = Field(max_length=100)
    available_refs: list[ExactOriginalRef] = Field(max_length=250)
    ledger: OperationCaseWorkspaceLedger
    external_effect_allowed: Literal[False] = False

    @field_validator("evaluated_at", "data_cutoff")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("operation case workspace time requires a timezone")
        return value

    @model_validator(mode="after")
    def _reconciles(self) -> "OperationCaseWorkspaceEnvelope":
        if [item.source_id for item in self.sources] != list(OperationCaseWorkspaceSourceId):
            raise ValueError("workspace sources must use canonical order")
        source_total = sum(
            item.count
            for item in self.sources
            if item.source_id is not OperationCaseWorkspaceSourceId.OPERATION_CASES
        )
        if source_total != self.ledger.source_total:
            raise ValueError("workspace source ledger drift")
        if len(self.available_refs) != self.ledger.unassigned:
            raise ValueError("available refs must equal unassigned ledger")
        case_counts = {
            OperationCaseStatus.OPEN: self.ledger.open_cases,
            OperationCaseStatus.PAUSED: self.ledger.paused_cases,
            OperationCaseStatus.CLOSED: self.ledger.closed_cases,
        }
        if any(
            sum(case.status is status for case in self.cases) != count
            for status, count in case_counts.items()
        ):
            raise ValueError("workspace case status ledger drift")
        blocked = sum(
            item.status is OperationCaseWorkspaceSourceStatus.BLOCKED
            for item in self.sources
        )
        if blocked == 0:
            expected = OperationCaseWorkspaceStatus.READY
        elif blocked == len(self.sources):
            expected = OperationCaseWorkspaceStatus.BLOCKED
        else:
            expected = OperationCaseWorkspaceStatus.PARTIAL
        if self.status is not expected:
            raise ValueError("workspace readiness drift")
        if len(self.candidates) != self.ledger.candidates:
            raise ValueError("workspace candidate ledger drift")
        return self


__all__ = [
    "OPERATION_CASE_WORKSPACE_SCHEMA_VERSION",
    "OperationCaseCandidateKind",
    "OperationCaseMemberLedger",
    "OperationCaseWorkspaceBlocker",
    "OperationCaseWorkspaceCandidate",
    "OperationCaseWorkspaceCase",
    "OperationCaseWorkspaceEnvelope",
    "OperationCaseWorkspaceLedger",
    "OperationCaseWorkspaceSource",
    "OperationCaseWorkspaceSourceId",
    "OperationCaseWorkspaceSourceStatus",
    "OperationCaseWorkspaceStatus",
]
