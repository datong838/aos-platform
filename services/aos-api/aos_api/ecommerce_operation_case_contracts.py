"""Strict W3-12A authority contracts for event-sourced operation cases."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext


Sha256 = str


def _require_aware(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("authority time requires a timezone")
    return value


class ExactOriginalRef(AipContractModel):
    tenant: TenantContext
    resource_type: Literal[
        "Order", "OrderLine", "ProductSku", "Shipment", "Payment", "AfterSalesEvent"
    ]
    resource_id: str = Field(min_length=1, max_length=300)
    content_hash: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    source_updated_at: datetime

    _aware_source_time = field_validator("source_updated_at")(_require_aware)


class ExactAuthorityRevisionRef(AipContractModel):
    resource_id: str = Field(min_length=1, max_length=300)
    revision: int = Field(ge=1)
    content_hash: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")


class AuthorityRevision(AipContractModel):
    tenant: TenantContext
    revision: int = Field(ge=1)
    content_hash: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    actor: str = Field(min_length=1, max_length=300)
    created_at: datetime

    _aware_created_at = field_validator("created_at")(_require_aware)


class OperationCaseStatus(StrEnum):
    OPEN = "open"
    PAUSED = "paused"
    CLOSED = "closed"


class OperationCaseRevision(AuthorityRevision):
    case_id: str = Field(min_length=1, max_length=300)
    version: int = Field(ge=1)
    status: OperationCaseStatus
    priority: Literal["low", "normal", "high", "critical"] = "normal"
    aggregation_policy_ref: ExactAuthorityRevisionRef
    member_refs: list[ExactOriginalRef]

    @model_validator(mode="after")
    def _unique_members(self) -> OperationCaseRevision:
        identities = [
            (
                item.tenant.org_id,
                item.tenant.project_id,
                item.resource_type,
                item.resource_id,
                item.content_hash,
            )
            for item in self.member_refs
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("operation case originals must be unique exact refs")
        return self


class OperationCaseEvent(AuthorityRevision):
    event_id: str = Field(min_length=1, max_length=300)
    case_ref: ExactAuthorityRevisionRef
    sequence: int = Field(ge=1)
    event_type: Literal[
        "created", "member_attached", "member_detached", "status_changed", "sla_changed"
    ]
    original_ref: ExactOriginalRef | None = None
    decision_ref: ExactAuthorityRevisionRef | None = None
    occurred_at: datetime

    _aware_occurred_at = field_validator("occurred_at")(_require_aware)


class OperationEventClassificationDecisionRevision(AuthorityRevision):
    decision_id: str = Field(min_length=1, max_length=300)
    original_ref: ExactOriginalRef
    classifier_ref: ExactAuthorityRevisionRef
    aggregation_policy_ref: ExactAuthorityRevisionRef
    classification: str = Field(min_length=1, max_length=120)
    confidence: float = Field(ge=0, le=1)
    evidence_refs: list[ExactAuthorityRevisionRef] = Field(default_factory=list)
    reason: str = Field(min_length=1, max_length=2000)


class AggregationPolicyRevision(AuthorityRevision):
    policy_id: str = Field(min_length=1, max_length=300)
    version: int = Field(ge=1)
    lifecycle: Literal["draft", "active", "revoked"]
    rule_hash: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    effective_from: datetime

    _aware_effective_from = field_validator("effective_from")(_require_aware)


class MembershipDecisionType(StrEnum):
    ATTACH = "attach"
    DETACH = "detach"
    SPLIT = "split"
    MERGE = "merge"
    REAGGREGATE = "reaggregate"


class CaseMembershipDecisionRevision(AuthorityRevision):
    decision_id: str = Field(min_length=1, max_length=300)
    decision_type: MembershipDecisionType
    predecessor_case_refs: list[ExactAuthorityRevisionRef] = Field(default_factory=list)
    successor_case_refs: list[ExactAuthorityRevisionRef] = Field(default_factory=list)
    moved_originals: list[ExactOriginalRef]
    before_total: int = Field(ge=0)
    after_total: int = Field(ge=0)
    unmatched_count: int = Field(ge=0)
    conflicted_count: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def _conserves_membership(self) -> CaseMembershipDecisionRevision:
        if self.before_total != self.after_total:
            raise ValueError("membership decision must preserve the originals multiset")
        reconciled_total = (
            len(self.moved_originals) + self.unmatched_count + self.conflicted_count
        )
        if self.before_total != reconciled_total:
            raise ValueError("membership count ledger must reconcile the originals multiset")
        if self.decision_type is MembershipDecisionType.SPLIT:
            if len(self.predecessor_case_refs) != 1 or len(self.successor_case_refs) < 2:
                raise ValueError("split requires one predecessor and at least two successors")
        if self.decision_type is MembershipDecisionType.MERGE:
            if len(self.predecessor_case_refs) < 2 or len(self.successor_case_refs) != 1:
                raise ValueError("merge requires at least two predecessors and one successor")
        return self


class SlaPolicyRevision(AuthorityRevision):
    policy_id: str = Field(min_length=1, max_length=300)
    version: int = Field(ge=1)
    lifecycle: Literal["draft", "active", "revoked"]
    response_seconds: int = Field(gt=0)
    resolution_seconds: int = Field(gt=0)
    effective_from: datetime

    _aware_effective_from = field_validator("effective_from")(_require_aware)


class SlaClockDecision(AuthorityRevision):
    decision_id: str = Field(min_length=1, max_length=300)
    case_ref: ExactAuthorityRevisionRef
    policy_ref: ExactAuthorityRevisionRef
    operation: Literal["start", "pause", "resume", "recompute"]
    source_event_time: datetime
    reason: str = Field(min_length=1, max_length=2000)

    _aware_source_event_time = field_validator("source_event_time")(_require_aware)


class KillCheckpoint(StrEnum):
    PROPOSAL = "proposal"
    LEASE = "lease"
    EXECUTOR = "executor"


class AutomationKillDecisionRevision(AuthorityRevision):
    decision_id: str = Field(min_length=1, max_length=300)
    state: Literal["active", "released"]
    scope_hash: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    checkpoints: list[KillCheckpoint]
    reason: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def _all_checkpoints(self) -> AutomationKillDecisionRevision:
        if set(self.checkpoints) != set(KillCheckpoint):
            raise ValueError("kill decision requires proposal, lease and executor checkpoints")
        if len(self.checkpoints) != len(KillCheckpoint):
            raise ValueError("kill decision checkpoints must be unique")
        return self


class OperationAuthorityReceipt(AipContractModel):
    tenant: TenantContext
    receipt_id: str = Field(min_length=1, max_length=300)
    operation: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=1, max_length=300)
    request_hash: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    result_ref: ExactAuthorityRevisionRef
    created_by: str = Field(min_length=1, max_length=300)
    created_at: datetime

    _aware_created_at = field_validator("created_at")(_require_aware)


__all__ = [
    "AggregationPolicyRevision",
    "AutomationKillDecisionRevision",
    "CaseMembershipDecisionRevision",
    "ExactAuthorityRevisionRef",
    "ExactOriginalRef",
    "KillCheckpoint",
    "OperationAuthorityReceipt",
    "OperationCaseEvent",
    "OperationCaseRevision",
    "OperationEventClassificationDecisionRevision",
    "SlaClockDecision",
    "SlaPolicyRevision",
]
