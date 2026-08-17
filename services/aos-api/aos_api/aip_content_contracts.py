"""Strict AIP-9 content-domain contracts.

The module freezes DTOs only.  It does not register routes, allocate stores,
call providers, render media, open avatar sessions, or authorize publication.
Tenant scope is response context and never accepted as request authority.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, ArtifactRef, ResourceRef, TenantContext
from aos_api.aip_production_contracts import (
    ContractBlocker,
    ContractReadiness,
    ExactRevisionRef,
    MutableAuthorityRef,
)


class ContentChannel(StrEnum):
    WEAPP = "weapp"
    DOUYIN = "douyin"
    KUAISHOU = "kuaishou"
    WECHAT_CHANNELS = "wechat_channels"
    XIAOHONGSHU = "xiaohongshu"


class ContentDeliverableKind(StrEnum):
    SEED_COPY = "seed_copy"
    SHORT_VIDEO = "short_video"
    LIVE_PLAN = "live_plan"
    PLATFORM_VARIANT = "platform_variant"


class MediaType(StrEnum):
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    SUBTITLE = "subtitle"
    FONT = "font"
    AVATAR = "avatar"
    DOCUMENT = "document"


class MediaUsage(StrEnum):
    INPUT = "input"
    OUTPUT = "output"
    REFERENCE = "reference"


class MediaJobKind(StrEnum):
    TTS = "tts"
    SUBTITLE = "subtitle"
    VIDEO_RENDER = "video_render"
    TRANSCODE = "transcode"
    THUMBNAIL = "thumbnail"


class MediaJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class MediaJobEventKind(StrEnum):
    CREATED = "created"
    CLAIMED = "claimed"
    HEARTBEAT = "heartbeat"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"
    RECONCILED = "reconciled"


class AvatarSessionStatus(StrEnum):
    OPENING = "opening"
    READY = "ready"
    LIVE = "live"
    PAUSED = "paused"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"
    KILLED = "killed"
    UNKNOWN = "unknown"


class AvatarSessionEventKind(StrEnum):
    OPENED = "opened"
    READY = "ready"
    HEARTBEAT = "heartbeat"
    LIVE = "live"
    PAUSED = "paused"
    RESUMED = "resumed"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"
    KILLED = "killed"
    UNKNOWN = "unknown"
    RECONCILED = "reconciled"


def _require_exact_resource(value: ResourceRef, label: str) -> ResourceRef:
    if not value.revision:
        raise ValueError(f"{label} requires an exact revision")
    return value


def _require_exact_artifact(value: ArtifactRef, label: str) -> ArtifactRef:
    if not value.revision:
        raise ValueError(f"{label}.revision is required")
    if not value.content_hash:
        raise ValueError(f"{label}.contentHash is required")
    return value


def _require_ref_kind(value: ExactRevisionRef, expected: str, label: str) -> None:
    if value.resource_type != expected:
        raise ValueError(f"{label} must reference {expected}")


class ContentBriefSpec(AipContractModel):
    """Typed ``TaskBriefRevision.spec`` for a content campaign."""

    brief_type: Literal["content_campaign"] = "content_campaign"
    objective: str = Field(min_length=1, max_length=1000)
    deliverable_kinds: list[ContentDeliverableKind] = Field(min_length=1, max_length=8)
    channel_targets: list[ContentChannel] = Field(min_length=1, max_length=8)
    product_refs: list[ResourceRef] = Field(min_length=1, max_length=100)
    audience_refs: list[ResourceRef] = Field(default_factory=list, max_length=100)
    evidence_bundle_ref: ExactRevisionRef
    factual_claim_policy: Literal["evidence_only"] = "evidence_only"
    content_constraints: dict[str, Any]
    cutoff_at: datetime

    @model_validator(mode="after")
    def _exact_facts_and_unique_targets(self) -> "ContentBriefSpec":
        _require_ref_kind(
            self.evidence_bundle_ref,
            "EvidenceBundleRevision",
            "evidenceBundleRef",
        )
        for index, ref in enumerate([*self.product_refs, *self.audience_refs]):
            _require_exact_resource(ref, f"factRefs[{index}]")
        if len(self.deliverable_kinds) != len(set(self.deliverable_kinds)):
            raise ValueError("deliverableKinds must be unique")
        if len(self.channel_targets) != len(set(self.channel_targets)):
            raise ValueError("channelTargets must be unique")
        return self


class ContentPipelineRefs(AipContractModel):
    """Exact composite projection over existing W2/AIP authorities."""

    brief_ref: ExactRevisionRef
    stage_template_ref: ExactRevisionRef
    responsibility_plan_ref: ExactRevisionRef
    eval_contract_ref: ExactRevisionRef
    model_route_ref: ExactRevisionRef | None = None
    runtime_policy_ref: ExactRevisionRef | None = None
    capability_refs: list[ExactRevisionRef] = Field(default_factory=list, max_length=100)
    tool_binding_refs: list[MutableAuthorityRef] = Field(default_factory=list, max_length=100)
    budget_ref: ExactRevisionRef | None = None
    readiness: ContractReadiness
    blockers: list[ContractBlocker] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def _exact_owner_mapping_and_honest_readiness(self) -> "ContentPipelineRefs":
        for value, expected, label in (
            (self.brief_ref, "TaskBriefRevision", "briefRef"),
            (self.stage_template_ref, "StageTemplateRevision", "stageTemplateRef"),
            (
                self.responsibility_plan_ref,
                "ResponsibilityPlanRevision",
                "responsibilityPlanRef",
            ),
            (self.eval_contract_ref, "EvalContractRevision", "evalContractRef"),
        ):
            _require_ref_kind(value, expected, label)
        if (self.model_route_ref is None) != (self.runtime_policy_ref is None):
            raise ValueError("modelRouteRef and runtimePolicyRef must be supplied together")
        if self.model_route_ref:
            _require_ref_kind(self.model_route_ref, "ModelRouteRevision", "modelRouteRef")
            _require_ref_kind(
                self.runtime_policy_ref,  # type: ignore[arg-type]
                "RuntimePolicyRevision",
                "runtimePolicyRef",
            )
        for ref in self.capability_refs:
            _require_ref_kind(ref, "CapabilityRevision", "capabilityRefs")
        for ref in self.tool_binding_refs:
            if ref.resource_type != "ToolBinding":
                raise ValueError("toolBindingRefs must reference ToolBinding")
        if self.budget_ref:
            _require_ref_kind(self.budget_ref, "BudgetRevision", "budgetRef")
        if self.readiness is ContractReadiness.READY and self.blockers:
            raise ValueError("ready pipeline cannot carry blockers")
        if self.readiness is not ContractReadiness.READY and not self.blockers:
            raise ValueError("non-ready pipeline requires blockers")
        if self.readiness is ContractReadiness.READY and (
            not self.model_route_ref or not self.capability_refs or not self.budget_ref
        ):
            raise ValueError(
                "ready pipeline requires model route, capability revisions and budget"
            )
        for label, refs in (
            ("capabilityRefs", self.capability_refs),
            ("toolBindingRefs", self.tool_binding_refs),
        ):
            identities = [
                (ref.resource_type, ref.resource_id, getattr(ref, "revision", None), getattr(ref, "version", None))
                for ref in refs
            ]
            if len(identities) != len(set(identities)):
                raise ValueError(f"{label} must be unique")
        return self


class MediaAssetRef(AipContractModel):
    """Reference-only media wrapper; binary payloads remain in Artifact authority."""

    artifact_ref: ArtifactRef
    media_type: MediaType
    usage: MediaUsage
    provenance_ref: ExactRevisionRef
    license_ref: ExactRevisionRef
    evidence_bundle_ref: ExactRevisionRef
    withdrawal_policy_ref: ExactRevisionRef

    @model_validator(mode="after")
    def _exact_governance_chain(self) -> "MediaAssetRef":
        _require_exact_artifact(self.artifact_ref, "artifactRef")
        for value, expected, label in (
            (self.provenance_ref, "AssetProvenanceRevision", "provenanceRef"),
            (self.license_ref, "AssetLicenseRevision", "licenseRef"),
            (self.evidence_bundle_ref, "EvidenceBundleRevision", "evidenceBundleRef"),
            (
                self.withdrawal_policy_ref,
                "AssetWithdrawalPolicyRevision",
                "withdrawalPolicyRef",
            ),
        ):
            _require_ref_kind(value, expected, label)
        if self.artifact_ref.artifact_type != self.media_type.value:
            raise ValueError("artifactRef.artifactType must match mediaType")
        return self


class ContentDraftProjection(AipContractModel):
    """Typed projection over ``aip_artifact``; never a second draft store."""

    artifact_ref: ArtifactRef
    brief_ref: ExactRevisionRef
    pipeline: ContentPipelineRefs
    variant_key: str = Field(min_length=1, max_length=160)
    channel: ContentChannel
    source_assets: list[MediaAssetRef] = Field(default_factory=list, max_length=100)
    evidence_bundle_ref: ExactRevisionRef
    eval_report_ref: ExactRevisionRef | None = None
    review_issue_refs: list[MutableAuthorityRef] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def _projection_owner_integrity(self) -> "ContentDraftProjection":
        _require_exact_artifact(self.artifact_ref, "artifactRef")
        if self.artifact_ref.artifact_type != "content_draft":
            raise ValueError("artifactRef.artifactType must be content_draft")
        _require_ref_kind(self.brief_ref, "TaskBriefRevision", "briefRef")
        _require_ref_kind(
            self.evidence_bundle_ref,
            "EvidenceBundleRevision",
            "evidenceBundleRef",
        )
        if self.eval_report_ref:
            _require_ref_kind(
                self.eval_report_ref,
                "EvalReportRevision",
                "evalReportRef",
            )
        if any(ref.resource_type != "ReviewIssue" for ref in self.review_issue_refs):
            raise ValueError("reviewIssueRefs must reference ReviewIssue")
        return self


class ContentDraftReadinessRequest(AipContractModel):
    brief_ref: ExactRevisionRef
    pipeline: ContentPipelineRefs
    task_run_ref: ResourceRef
    agent_run_ref: ResourceRef
    variant_key: str = Field(min_length=1, max_length=160)
    channel: ContentChannel

    @model_validator(mode="after")
    def _exact_runtime_refs(self) -> "ContentDraftReadinessRequest":
        _require_ref_kind(self.brief_ref, "TaskBriefRevision", "briefRef")
        for value, expected, label in (
            (self.task_run_ref, "TaskRun", "taskRunRef"),
            (self.agent_run_ref, "AgentRun", "agentRunRef"),
        ):
            _require_exact_resource(value, label)
            if value.resource_type != expected:
                raise ValueError(f"{label} must reference {expected}")
        if self.pipeline.brief_ref != self.brief_ref:
            raise ValueError("pipeline.briefRef must equal briefRef")
        return self


class ContentDraftReadinessDecision(AipContractModel):
    tenant: TenantContext
    readiness: ContractReadiness
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    dependency_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    blockers: list[ContractBlocker] = Field(default_factory=list, max_length=100)
    evaluated_at: datetime

    @model_validator(mode="after")
    def _honest_readiness(self) -> "ContentDraftReadinessDecision":
        if self.readiness is ContractReadiness.READY and self.blockers:
            raise ValueError("ready decision cannot carry blockers")
        if self.readiness is not ContractReadiness.READY and not self.blockers:
            raise ValueError("non-ready decision requires blockers")
        return self


class GovernedContentObjectRef(AipContractModel):
    content_ref: str = Field(min_length=1, max_length=2048)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_ref: ResourceRef
    byte_size: int = Field(ge=1)
    media_type: Literal["text/plain", "text/markdown", "application/json"]
    marking: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def _exact_schema(self) -> "GovernedContentObjectRef":
        _require_exact_resource(self.schema_ref, "schemaRef")
        return self


class ContentDraftRegisterRequest(AipContractModel):
    readiness_request: ContentDraftReadinessRequest
    content_object: GovernedContentObjectRef
    prompt_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_bundle_ref: ExactRevisionRef
    source_assets: list[MediaAssetRef] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def _exact_sources(self) -> "ContentDraftRegisterRequest":
        _require_ref_kind(
            self.evidence_bundle_ref,
            "EvidenceBundleRevision",
            "evidenceBundleRef",
        )
        return self


class ContentDraftRegistrationReceipt(AipContractModel):
    tenant: TenantContext
    receipt_id: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_ref: str = Field(min_length=1, max_length=2048)
    draft: ContentDraftProjection
    created_at: datetime


class MediaJobCreateRequest(AipContractModel):
    task_run_ref: ResourceRef
    step_run_ref: ResourceRef
    job_kind: MediaJobKind
    input_assets: list[MediaAssetRef] = Field(min_length=1, max_length=100)
    output_schema_ref: ResourceRef
    capability_ref: ExactRevisionRef
    capability_binding_ref: MutableAuthorityRef
    budget_ref: ExactRevisionRef
    deadline_at: datetime

    @model_validator(mode="after")
    def _runtime_refs(self) -> "MediaJobCreateRequest":
        for value, expected, label in (
            (self.task_run_ref, "TaskRun", "taskRunRef"),
            (self.step_run_ref, "StepRun", "stepRunRef"),
        ):
            _require_exact_resource(value, label)
            if value.resource_type != expected:
                raise ValueError(f"{label} must reference {expected}")
        _require_exact_resource(self.output_schema_ref, "outputSchemaRef")
        _require_ref_kind(self.capability_ref, "CapabilityRevision", "capabilityRef")
        if self.capability_binding_ref.resource_type != "CapabilityBinding":
            raise ValueError("capabilityBindingRef must reference CapabilityBinding")
        return self


class MediaJobSnapshot(AipContractModel):
    tenant: TenantContext
    job_id: str = Field(min_length=1, max_length=240)
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_run_ref: ResourceRef
    step_run_ref: ResourceRef
    job_kind: MediaJobKind
    attempt: int = Field(ge=1)
    status: MediaJobStatus
    latest_sequence: int = Field(ge=1)
    executor_lease_ref: ResourceRef | None = None
    heartbeat_at: datetime | None = None
    lease_expires_at: datetime | None = None
    output_artifact_refs: list[ArtifactRef] = Field(default_factory=list, max_length=100)
    completion_receipt_ref: ExactRevisionRef | None = None
    blockers: list[ContractBlocker] = Field(default_factory=list, max_length=100)
    reason_code: str | None = Field(default=None, min_length=1, max_length=160)
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None

    @model_validator(mode="after")
    def _honest_job_state(self) -> "MediaJobSnapshot":
        _require_exact_resource(self.task_run_ref, "taskRunRef")
        _require_exact_resource(self.step_run_ref, "stepRunRef")
        lease_values = (self.executor_lease_ref, self.heartbeat_at, self.lease_expires_at)
        if self.status is MediaJobStatus.RUNNING:
            if any(value is None for value in lease_values):
                raise ValueError("running media job requires lease, heartbeat and expiry")
            _require_exact_resource(self.executor_lease_ref, "executorLeaseRef")  # type: ignore[arg-type]
            if self.lease_expires_at <= self.heartbeat_at:  # type: ignore[operator]
                raise ValueError("media job lease expiry must be after heartbeat")
        elif any(value is not None for value in lease_values):
            raise ValueError("non-running media job cannot carry an executor lease")

        if self.status is MediaJobStatus.SUCCEEDED:
            if not self.output_artifact_refs or not self.completion_receipt_ref or not self.finished_at:
                raise ValueError(
                    "succeeded media job requires output artifacts, completion receipt and finishedAt"
                )
            for artifact in self.output_artifact_refs:
                _require_exact_artifact(artifact, "outputArtifactRefs")
            _require_ref_kind(
                self.completion_receipt_ref,
                "MediaJobReceipt",
                "completionReceiptRef",
            )
            if self.blockers or self.reason_code:
                raise ValueError("succeeded media job cannot carry blockers or reasonCode")
        elif self.output_artifact_refs:
            raise ValueError("only succeeded media job can carry outputArtifactRefs")

        if self.status in {MediaJobStatus.FAILED, MediaJobStatus.CANCELLED}:
            if not self.reason_code or not self.completion_receipt_ref or not self.finished_at:
                raise ValueError("failed/cancelled media job requires reason, receipt and finishedAt")
            _require_ref_kind(
                self.completion_receipt_ref,
                "MediaJobReceipt",
                "completionReceiptRef",
            )
        if self.status is MediaJobStatus.UNKNOWN and (not self.blockers or self.finished_at):
            raise ValueError("unknown media job requires blockers and remains unfinished")
        if self.status in {MediaJobStatus.QUEUED, MediaJobStatus.RUNNING} and self.finished_at:
            raise ValueError("active media job cannot carry finishedAt")
        if self.updated_at < self.created_at:
            raise ValueError("updatedAt must not precede createdAt")
        return self


class AvatarSessionOpenRequest(AipContractModel):
    task_run_ref: ResourceRef
    step_run_ref: ResourceRef
    capability_ref: ExactRevisionRef
    capability_binding_ref: MutableAuthorityRef
    budget_ref: ExactRevisionRef
    kill_policy_ref: ExactRevisionRef
    live_plan_ref: ArtifactRef
    max_duration_seconds: int = Field(ge=1, le=21_600)

    @model_validator(mode="after")
    def _session_authorities(self) -> "AvatarSessionOpenRequest":
        for value, expected, label in (
            (self.task_run_ref, "TaskRun", "taskRunRef"),
            (self.step_run_ref, "StepRun", "stepRunRef"),
        ):
            _require_exact_resource(value, label)
            if value.resource_type != expected:
                raise ValueError(f"{label} must reference {expected}")
        _require_ref_kind(self.capability_ref, "CapabilityRevision", "capabilityRef")
        if self.capability_binding_ref.resource_type != "CapabilityBinding":
            raise ValueError("capabilityBindingRef must reference CapabilityBinding")
        _require_exact_artifact(self.live_plan_ref, "livePlanRef")
        return self


class AvatarSessionSnapshot(AipContractModel):
    tenant: TenantContext
    session_id: str = Field(min_length=1, max_length=240)
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_run_ref: ResourceRef
    step_run_ref: ResourceRef
    capability_binding_ref: MutableAuthorityRef
    budget_ref: ExactRevisionRef
    kill_policy_ref: ExactRevisionRef
    max_duration_seconds: int = Field(ge=1, le=21_600)
    status: AvatarSessionStatus
    latest_sequence: int = Field(ge=1)
    engine_session_ref: ExactRevisionRef | None = None
    human_heartbeat_at: datetime | None = None
    human_heartbeat_expires_at: datetime | None = None
    completion_receipt_ref: ExactRevisionRef | None = None
    blockers: list[ContractBlocker] = Field(default_factory=list, max_length=100)
    reason_code: str | None = Field(default=None, min_length=1, max_length=160)
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None

    @model_validator(mode="after")
    def _honest_session_state(self) -> "AvatarSessionSnapshot":
        _require_exact_resource(self.task_run_ref, "taskRunRef")
        _require_exact_resource(self.step_run_ref, "stepRunRef")
        if self.capability_binding_ref.resource_type != "CapabilityBinding":
            raise ValueError("capabilityBindingRef must reference CapabilityBinding")
        heartbeat_pair = (self.human_heartbeat_at, self.human_heartbeat_expires_at)
        if self.status is AvatarSessionStatus.LIVE:
            if any(value is None for value in heartbeat_pair):
                raise ValueError("live avatar session requires human heartbeat and expiry")
            if self.human_heartbeat_expires_at <= self.human_heartbeat_at:  # type: ignore[operator]
                raise ValueError("human heartbeat expiry must be after heartbeat")
            if not self.engine_session_ref:
                raise ValueError("live avatar session requires opaque engineSessionRef")
            _require_ref_kind(
                self.engine_session_ref,
                "OpaqueAvatarEngineSessionRef",
                "engineSessionRef",
            )
        elif any(value is not None for value in heartbeat_pair):
            raise ValueError("non-live avatar session cannot carry human heartbeat")

        terminal = {
            AvatarSessionStatus.CLOSED,
            AvatarSessionStatus.FAILED,
            AvatarSessionStatus.KILLED,
        }
        if self.status in terminal:
            if not self.finished_at or not self.completion_receipt_ref:
                raise ValueError("terminal avatar session requires receipt and finishedAt")
            _require_ref_kind(
                self.completion_receipt_ref,
                "AvatarSessionReceipt",
                "completionReceiptRef",
            )
            if self.status in {AvatarSessionStatus.FAILED, AvatarSessionStatus.KILLED} and not self.reason_code:
                raise ValueError("failed/killed avatar session requires reasonCode")
        elif self.finished_at or self.completion_receipt_ref:
            raise ValueError("non-terminal avatar session cannot carry completion fields")
        if self.status is AvatarSessionStatus.UNKNOWN and not self.blockers:
            raise ValueError("unknown avatar session requires blockers")
        if self.updated_at < self.created_at:
            raise ValueError("updatedAt must not precede createdAt")
        return self


class PublishProposalPayload(AipContractModel):
    """Payload for AIP-3 ActionProposal; this contract cannot publish."""

    action_type: Literal["publish_content"] = "publish_content"
    content_draft_ref: ArtifactRef
    channel: ContentChannel
    account_ref: MutableAuthorityRef
    harness_revision_ref: ExactRevisionRef
    impact_preview_ref: ExactRevisionRef
    evidence_bundle_ref: ExactRevisionRef
    requested_mode: Literal["proposal_only"] = "proposal_only"
    scheduled_at: datetime | None = None

    @model_validator(mode="after")
    def _proposal_only_authorities(self) -> "PublishProposalPayload":
        _require_exact_artifact(self.content_draft_ref, "contentDraftRef")
        if self.content_draft_ref.artifact_type != "content_draft":
            raise ValueError("contentDraftRef.artifactType must be content_draft")
        if self.account_ref.resource_type != "PlatformAccountBinding":
            raise ValueError("accountRef must reference PlatformAccountBinding")
        for value, expected, label in (
            (self.harness_revision_ref, "PlatformHarnessRevision", "harnessRevisionRef"),
            (self.impact_preview_ref, "ImpactPreviewRevision", "impactPreviewRef"),
            (self.evidence_bundle_ref, "EvidenceBundleRevision", "evidenceBundleRef"),
        ):
            _require_ref_kind(value, expected, label)
        return self


__all__ = [
    "AvatarSessionEventKind",
    "AvatarSessionOpenRequest",
    "AvatarSessionSnapshot",
    "AvatarSessionStatus",
    "ContentBriefSpec",
    "ContentChannel",
    "ContentDeliverableKind",
    "ContentDraftProjection",
    "ContentPipelineRefs",
    "MediaAssetRef",
    "MediaJobCreateRequest",
    "MediaJobEventKind",
    "MediaJobKind",
    "MediaJobSnapshot",
    "MediaJobStatus",
    "MediaType",
    "MediaUsage",
    "PublishProposalPayload",
]
