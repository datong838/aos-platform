"""Fail-closed G5/G6 connector and governed Action composition.

This SolutionPack compiler only produces review drafts from exact references.
It never calls a connector, Provider, Tool or Action executor and never writes
business data, memory or Wiki content.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, ActionRiskLevel, TenantContext
from aos_api.aip_ecommerce_growth_core_agents import (
    SourceReadinessGateSnapshot,
    SourceReadinessStatus,
)
from aos_api.aip_production_contracts import ContractBlocker, ExactRevisionRef


_UNSAFE_TEXT = re.compile(
    r"(?:\b1[3-9]\d{9}\b|\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|"
    r"(?:openid|open_id|mobile|phone|address|cookie|token|api[_ -]?key|secret)\s*[:=：]?|"
    r"ignore\s+(?:all\s+)?previous|reveal\s+(?:the\s+)?system\s+prompt|"
    r"jailbreak|忽略(?:以上|之前)|泄露系统提示词)",
    re.IGNORECASE,
)


def _exact(value: ExactRevisionRef, kind: str, label: str) -> None:
    if value.resource_type != kind:
        raise ValueError(f"{label} must reference {kind}")


def _aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


def _digest(*values: str) -> str:
    return hashlib.sha256("\x1f".join(values).encode()).hexdigest()


def _block(code: str, message: str, ref: ExactRevisionRef | None = None) -> ContractBlocker:
    return ContractBlocker(code=code, message=message, resource_ref=ref)


class CapabilityState(StrEnum):
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"
    MANUAL_ONLY = "manual_only"
    READ_ONLY = "read_only"
    WRITE_REQUIRES_REVIEW = "write_requires_review"
    SUPPORTED = "supported"


class OperationOutcome(StrEnum):
    DRAFT = "draft"
    ACCEPTED = "accepted"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class KillGateState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class ConnectorState(StrEnum):
    READY_FOR_REVIEW = "ready_for_review"
    BLOCKED = "blocked"
    RECONCILE_REQUIRED = "reconcile_required"


class G5G6LogicStage(AipContractModel):
    order: int = Field(ge=1, le=2)
    logic_id: str = Field(pattern=r"^G0[56]$")
    logic_ref: ExactRevisionRef

    @model_validator(mode="after")
    def _canonical(self) -> "G5G6LogicStage":
        _exact(self.logic_ref, "LogicGraphRevision", "logicRef")
        if self.logic_ref.resource_id != f"ecommerce.logic.{self.logic_id}":
            raise ValueError("logicRef must bind canonical ecommerce Logic ID")
        return self


class PlatformCapabilitySnapshot(AipContractModel):
    platform: str = Field(min_length=1, max_length=80)
    installation_ref: ExactRevisionRef
    capability_ref: ExactRevisionRef
    capability_key: str = Field(min_length=1, max_length=160)
    operation: str = Field(min_length=1, max_length=160)
    state: CapabilityState
    official_evidence_ref: ExactRevisionRef | None = None
    verified_at: datetime
    fresh_until: datetime
    supports_status_query: bool
    supports_idempotency: bool
    supports_reconcile: bool
    supports_compensation: bool

    @model_validator(mode="after")
    def _authority(self) -> "PlatformCapabilitySnapshot":
        _exact(self.installation_ref, "ConnectorInstallationRevision", "installationRef")
        _exact(self.capability_ref, "ConnectorCapabilitySnapshotRevision", "capabilityRef")
        _aware(self.verified_at, "verifiedAt")
        _aware(self.fresh_until, "freshUntil")
        if self.fresh_until <= self.verified_at:
            raise ValueError("freshUntil must follow verifiedAt")
        if self.state is CapabilityState.UNKNOWN:
            if self.official_evidence_ref is not None:
                _exact(self.official_evidence_ref, "OfficialCapabilityEvidenceRevision", "officialEvidenceRef")
        else:
            if self.official_evidence_ref is None:
                raise ValueError("non-UNKNOWN capability requires official evidence")
            _exact(self.official_evidence_ref, "OfficialCapabilityEvidenceRevision", "officialEvidenceRef")
        return self


class WebhookSecuritySnapshot(AipContractModel):
    webhook_policy_ref: ExactRevisionRef
    signature_verified: bool
    timestamp_verified: bool
    nonce_replay_checked: bool
    body_hash_verified: bool
    schema_compatible: bool
    received_at: datetime

    @model_validator(mode="after")
    def _refs(self) -> "WebhookSecuritySnapshot":
        _exact(self.webhook_policy_ref, "WebhookSecurityPolicyRevision", "webhookPolicyRef")
        _aware(self.received_at, "receivedAt")
        return self


class KillGateSnapshot(AipContractModel):
    policy_ref: ExactRevisionRef
    proposal_gate: KillGateState
    reserve_gate: KillGateState
    invoke_gate: KillGateState
    checked_at: datetime
    fresh_until: datetime

    @model_validator(mode="after")
    def _policy(self) -> "KillGateSnapshot":
        _exact(self.policy_ref, "ActionKillPolicyRevision", "policyRef")
        _aware(self.checked_at, "checkedAt")
        _aware(self.fresh_until, "freshUntil")
        if self.fresh_until <= self.checked_at:
            raise ValueError("freshUntil must follow checkedAt")
        return self


class ActionControlSnapshot(AipContractModel):
    proposal_ref: ExactRevisionRef
    proposal_version: int = Field(ge=1)
    expected_proposal_version: int = Field(ge=1)
    proposal_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_proposal_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    actual_payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    proposal_status: str = Field(min_length=1, max_length=40)
    risk_level: ActionRiskLevel
    maker_actor: str = Field(min_length=1, max_length=160)
    approval_refs: list[ExactRevisionRef] = Field(default_factory=list, max_length=8)
    approver_actors: list[str] = Field(default_factory=list, max_length=8)
    minimum_approvals: int = Field(ge=0, le=8)
    proposal_expires_at: datetime
    lease_ref: ExactRevisionRef
    lease_attempt: int = Field(ge=1)
    lease_expires_at: datetime
    kill_gate: KillGateSnapshot

    @model_validator(mode="after")
    def _refs(self) -> "ActionControlSnapshot":
        _exact(self.proposal_ref, "ActionProposalRevision", "proposalRef")
        _exact(self.lease_ref, "ExecutionLeaseRevision", "leaseRef")
        for item in self.approval_refs:
            _exact(item, "ApprovalEventRevision", "approvalRefs")
        _aware(self.proposal_expires_at, "proposalExpiresAt")
        _aware(self.lease_expires_at, "leaseExpiresAt")
        if len(self.approval_refs) != len(self.approver_actors):
            raise ValueError("approval refs and actors must have equal length")
        if len(set(self.approver_actors)) != len(self.approver_actors):
            raise ValueError("approver actors must be unique")
        return self


class ConnectorActionInput(AipContractModel):
    source_readiness: SourceReadinessGateSnapshot
    logic_stages: list[G5G6LogicStage] = Field(min_length=2, max_length=2)
    capability: PlatformCapabilitySnapshot
    webhook_security: WebhookSecuritySnapshot
    action_control: ActionControlSnapshot
    artifact_ref: ExactRevisionRef
    live_plan_ref: ExactRevisionRef
    avatar_session_ref: ExactRevisionRef
    harness_ref: ExactRevisionRef
    operation_outcome: OperationOutcome
    requested_at: datetime
    purpose_summary: str = Field(min_length=1, max_length=600)
    compensation_requested: bool = False

    @field_validator("purpose_summary")
    @classmethod
    def _safe_summary(cls, value: str) -> str:
        cleaned = value.strip()
        if _UNSAFE_TEXT.search(cleaned):
            raise ValueError("purpose summary contains sensitive or injected content")
        return cleaned

    @model_validator(mode="after")
    def _refs(self) -> "ConnectorActionInput":
        for value, kind, label in (
            (self.artifact_ref, "ArtifactRevision", "artifactRef"),
            (self.live_plan_ref, "LivePlanRevision", "livePlanRef"),
            (self.avatar_session_ref, "AvatarSessionRevision", "avatarSessionRef"),
            (self.harness_ref, "HarnessRevision", "harnessRef"),
        ):
            _exact(value, kind, label)
        _aware(self.requested_at, "requestedAt")
        return self


class ConnectorDraft(AipContractModel):
    status: Literal["draft"] = "draft"
    platform: str
    capability_ref: ExactRevisionRef
    installation_ref: ExactRevisionRef
    artifact_ref: ExactRevisionRef
    live_plan_ref: ExactRevisionRef
    avatar_session_ref: ExactRevisionRef
    harness_ref: ExactRevisionRef
    draft_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    platform_write_authorized: Literal[False] = False


class WebhookReviewDraft(AipContractModel):
    status: Literal["draft"] = "draft"
    webhook_policy_ref: ExactRevisionRef
    quarantined: bool
    business_payload_write_authorized: Literal[False] = False
    action_trigger_authorized: Literal[False] = False


class ActionReviewDraft(AipContractModel):
    status: Literal["draft"] = "draft"
    proposal_ref: ExactRevisionRef
    lease_ref: ExactRevisionRef
    operation_outcome: OperationOutcome
    reconcile_required: bool
    automatic_retry_authorized: Literal[False] = False
    external_execution_authorized: Literal[False] = False


class CompensationProposalDraft(AipContractModel):
    status: Literal["draft"] = "draft"
    source_proposal_ref: ExactRevisionRef
    separate_action_proposal_required: Literal[True] = True
    direct_reverse_execution_authorized: Literal[False] = False


class G5G6Compilation(AipContractModel):
    tenant: TenantContext
    state: ConnectorState
    blockers: list[ContractBlocker]
    connector_draft: ConnectorDraft
    webhook_draft: WebhookReviewDraft
    action_review_draft: ActionReviewDraft
    compensation_draft: CompensationProposalDraft | None = None
    external_connector_called: Literal[False] = False
    action_executed: Literal[False] = False
    database_written: Literal[False] = False
    memory_written: Literal[False] = False
    wiki_written: Literal[False] = False
    production_written: Literal[False] = False

    @model_validator(mode="after")
    def _honest(self) -> "G5G6Compilation":
        if self.state is ConnectorState.READY_FOR_REVIEW and self.blockers:
            raise ValueError("ready compilation cannot contain blockers")
        if self.state is ConnectorState.RECONCILE_REQUIRED:
            if not self.action_review_draft.reconcile_required:
                raise ValueError("reconcile state requires reconcile draft")
        return self


def _blockers(value: ConnectorActionInput) -> list[ContractBlocker]:
    blockers: list[ContractBlocker] = []
    if value.source_readiness.status is not SourceReadinessStatus.READY:
        blockers.append(_block("G5G6_SOURCE_READINESS_NOT_READY", "SourceReadiness is not 12/12 READY", value.source_readiness.evidence_pack_ref))
    if value.source_readiness.fresh_until <= value.requested_at:
        blockers.append(_block("G5G6_SOURCE_READINESS_STALE", "SourceReadiness evidence is stale", value.source_readiness.evidence_pack_ref))
    if [(item.order, item.logic_id) for item in value.logic_stages] != [(1, "G05"), (2, "G06")]:
        blockers.append(_block("G5G6_LOGIC_SEQUENCE_INVALID", "G05 and G06 exact sequence is required"))
    if value.capability.state not in {CapabilityState.WRITE_REQUIRES_REVIEW, CapabilityState.SUPPORTED}:
        blockers.append(_block("G5_CAPABILITY_NOT_WRITE_READY", "platform capability is unknown, unsupported or non-write", value.capability.capability_ref))
    if value.capability.fresh_until <= value.requested_at:
        blockers.append(_block("G5_CAPABILITY_EVIDENCE_STALE", "official capability evidence is stale", value.capability.capability_ref))
    webhook_checks = (
        (value.webhook_security.signature_verified, "G5_WEBHOOK_SIGNATURE_UNVERIFIED"),
        (value.webhook_security.timestamp_verified, "G5_WEBHOOK_TIMESTAMP_UNVERIFIED"),
        (value.webhook_security.nonce_replay_checked, "G5_WEBHOOK_REPLAY_UNCHECKED"),
        (value.webhook_security.body_hash_verified, "G5_WEBHOOK_BODY_HASH_UNVERIFIED"),
        (value.webhook_security.schema_compatible, "G5_WEBHOOK_SCHEMA_INCOMPATIBLE"),
    )
    for passed, code in webhook_checks:
        if not passed:
            blockers.append(_block(code, "webhook security gate failed closed", value.webhook_security.webhook_policy_ref))
    action = value.action_control
    if action.proposal_version != action.expected_proposal_version or action.proposal_hash != action.expected_proposal_hash:
        blockers.append(_block("G6_ACTION_PROPOSAL_EXACT_REF_DRIFT", "ActionProposal version or hash drifted", action.proposal_ref))
    if action.actual_payload_hash != action.expected_payload_hash:
        blockers.append(_block("G6_ACTION_PAYLOAD_HASH_DRIFT", "Action payload hash drifted", action.proposal_ref))
    if action.proposal_status != "approved":
        blockers.append(_block("G6_PROPOSAL_NOT_APPROVED", "ActionProposal is not approved", action.proposal_ref))
    if action.proposal_expires_at <= value.requested_at:
        blockers.append(_block("G6_PROPOSAL_EXPIRED", "ActionProposal is expired", action.proposal_ref))
    if action.risk_level in {ActionRiskLevel.R2, ActionRiskLevel.R3, ActionRiskLevel.R4} and action.maker_actor in action.approver_actors:
        blockers.append(_block("G6_MAKER_CHECKER_VIOLATION", "maker cannot approve the same proposal", action.proposal_ref))
    risk_minimum = 2 if action.risk_level in {ActionRiskLevel.R3, ActionRiskLevel.R4} else (1 if action.risk_level is ActionRiskLevel.R2 else 0)
    if action.minimum_approvals < risk_minimum:
        blockers.append(_block("G6_APPROVAL_POLICY_BELOW_RISK_FLOOR", "approval policy is below the server risk floor", action.proposal_ref))
    if len(action.approval_refs) < max(action.minimum_approvals, risk_minimum):
        blockers.append(_block("G6_APPROVALS_INSUFFICIENT", "approval count is below policy minimum", action.proposal_ref))
    if action.risk_level is ActionRiskLevel.R4:
        blockers.append(_block("G6_R4_PERMANENTLY_BLOCKED", "common G6 never executes R4 actions", action.proposal_ref))
    if action.lease_expires_at <= value.requested_at:
        blockers.append(_block("G6_LEASE_EXPIRED", "ExecutionLease is expired", action.lease_ref))
    if action.lease_attempt != 1:
        blockers.append(_block("G6_LEASE_ATTEMPT_NOT_INITIAL", "common G6 permits only the first immutable attempt", action.lease_ref))
    if action.kill_gate.fresh_until <= value.requested_at:
        blockers.append(_block("G6_KILL_GATE_STALE", "kill gate snapshot is stale", action.kill_gate.policy_ref))
    for field in ("proposal_gate", "reserve_gate", "invoke_gate"):
        if getattr(action.kill_gate, field) is not KillGateState.OPEN:
            blockers.append(_block(f"G6_KILL_{field.upper()}", "kill gate is closed or unknown", action.kill_gate.policy_ref))
    for passed, code in (
        (value.capability.supports_status_query, "G6_STATUS_QUERY_UNVERIFIED"),
        (value.capability.supports_idempotency, "G6_IDEMPOTENCY_UNVERIFIED"),
        (value.capability.supports_reconcile, "G6_RECONCILE_UNVERIFIED"),
    ):
        if not passed:
            blockers.append(_block(code, "required operational safety capability is unverified", value.capability.capability_ref))
    if value.operation_outcome is OperationOutcome.UNKNOWN:
        blockers.append(_block("G6_OUTCOME_UNKNOWN_RECONCILE_REQUIRED", "unknown outcome requires provider reread and reconciliation", action.proposal_ref))
    return blockers


def compile_connector_action_governance(
    tenant: TenantContext,
    value: ConnectorActionInput,
) -> G5G6Compilation:
    """Compile G5/G6 review drafts without any external or persistent effect."""

    blockers = _blockers(value)
    webhook_quarantined = any(item.code.startswith("G5_WEBHOOK_") for item in blockers)
    state = ConnectorState.BLOCKED if blockers else ConnectorState.READY_FOR_REVIEW
    if value.operation_outcome is OperationOutcome.UNKNOWN:
        state = ConnectorState.RECONCILE_REQUIRED
    return G5G6Compilation(
        tenant=tenant,
        state=state,
        blockers=blockers,
        connector_draft=ConnectorDraft(
            platform=value.capability.platform,
            capability_ref=value.capability.capability_ref,
            installation_ref=value.capability.installation_ref,
            artifact_ref=value.artifact_ref,
            live_plan_ref=value.live_plan_ref,
            avatar_session_ref=value.avatar_session_ref,
            harness_ref=value.harness_ref,
            draft_digest=_digest(
                value.capability.capability_ref.content_hash,
                value.artifact_ref.content_hash,
                value.action_control.proposal_hash,
                value.purpose_summary,
            ),
        ),
        webhook_draft=WebhookReviewDraft(
            webhook_policy_ref=value.webhook_security.webhook_policy_ref,
            quarantined=webhook_quarantined,
        ),
        action_review_draft=ActionReviewDraft(
            proposal_ref=value.action_control.proposal_ref,
            lease_ref=value.action_control.lease_ref,
            operation_outcome=value.operation_outcome,
            reconcile_required=value.operation_outcome is OperationOutcome.UNKNOWN,
        ),
        compensation_draft=(
            CompensationProposalDraft(source_proposal_ref=value.action_control.proposal_ref)
            if value.compensation_requested
            else None
        ),
    )


__all__ = [
    "ActionControlSnapshot",
    "CapabilityState",
    "ConnectorActionInput",
    "ConnectorState",
    "G5G6Compilation",
    "G5G6LogicStage",
    "KillGateSnapshot",
    "OperationOutcome",
    "PlatformCapabilitySnapshot",
    "WebhookSecuritySnapshot",
    "compile_connector_action_governance",
]
