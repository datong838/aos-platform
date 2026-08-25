"""Strict W7-09 Media Studio lifecycle contribution contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.aip_media_responsibility_capability_map import (
    MEDIA_RESPONSIBILITY_CAPABILITY_MAP,
)


MEDIA_STUDIO_LIFECYCLE_SCHEMA_VERSION = "aos.ecommerce-workshop.media-studio-lifecycle/v1"


class MediaLifecycleNodeId(StrEnum):
    PREPARE = "prepare"
    FREEZE_CONFIRM = "freeze_confirm"
    COMPILE_APPROVE = "compile_approve"
    START_RUN = "start_run"
    REVIEW_RETURN = "review_return"
    DELIVER_PUBLISH = "deliver_publish"
    RECONCILE_EFFECT = "reconcile_effect"


class MediaContributionStatus(StrEnum):
    READY = "ready"
    ACTIVE = "active"
    BLOCKED = "blocked"
    NOT_STARTED = "not_started"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"
    NOT_APPLICABLE = "not_applicable"


class MediaLifecycleAuthorityRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class MediaLifecycleNodeContribution(AipContractModel):
    node_id: MediaLifecycleNodeId
    label: str = Field(min_length=1, max_length=120)
    status: MediaContributionStatus
    authority_refs: list[MediaLifecycleAuthorityRef] = Field(default_factory=list, max_length=20)
    blocker_codes: list[str] = Field(default_factory=list, max_length=40)
    observed_at: datetime | None = None

    @field_validator("observed_at")
    @classmethod
    def _aware_observed_at(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("lifecycle observation requires timezone")
        return value

    @model_validator(mode="after")
    def _honest_status(self) -> "MediaLifecycleNodeContribution":
        if self.status in {MediaContributionStatus.READY, MediaContributionStatus.ACTIVE} and not self.authority_refs:
            raise ValueError("ready or active lifecycle node requires authority")
        if self.status in {MediaContributionStatus.BLOCKED, MediaContributionStatus.UNKNOWN, MediaContributionStatus.CONFLICT} and not self.blocker_codes:
            raise ValueError("non-ready lifecycle node requires blockers")
        return self


class MediaResponsibilityContribution(AipContractModel):
    slot_id: str = Field(pattern=r"^media[.][a-z0-9-]+$")
    label: str = Field(min_length=1, max_length=80)
    responsibility_type: str = Field(min_length=1, max_length=160)
    status: Literal["assigned", "blocked"]
    required_capability_ids: list[str] = Field(min_length=1, max_length=16)
    assignee_kind: str | None = Field(default=None, min_length=1, max_length=80)
    assignee_id: str | None = Field(default=None, min_length=1, max_length=200)
    assignee_version: int | None = Field(default=None, ge=1)
    resolution_receipt_id: str | None = Field(default=None, min_length=1, max_length=240)
    blocker_codes: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _assignment_is_complete(self) -> "MediaResponsibilityContribution":
        assignment = (self.assignee_kind, self.assignee_id, self.assignee_version, self.resolution_receipt_id)
        if self.status == "assigned":
            if any(item is None for item in assignment) or self.blocker_codes:
                raise ValueError("assigned responsibility requires assignee and resolution receipt")
        elif any(item is not None for item in assignment) or not self.blocker_codes:
            raise ValueError("blocked responsibility cannot carry partial assignment")
        return self


class MediaStageContribution(AipContractModel):
    stage_id: str = Field(min_length=1, max_length=200)
    task_run_id: str = Field(min_length=1, max_length=200)
    attempt: int = Field(ge=1)
    status: str = Field(min_length=1, max_length=80)
    capability_ref: MediaLifecycleAuthorityRef
    colleague_binding_ref: MediaLifecycleAuthorityRef
    provider_ref: MediaLifecycleAuthorityRef
    provider_job_id: str = Field(min_length=1, max_length=200)
    blocker_codes: list[str] = Field(default_factory=list, max_length=40)
    external_effects_allowed: Literal[False] = False


class MediaArtifactFamilyContribution(AipContractModel):
    family_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)
    topology_status: str = Field(min_length=1, max_length=80)
    member_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    gate_set_count: int = Field(ge=0)
    latest_gate_readiness: str | None = Field(default=None, min_length=1, max_length=80)
    issue_count: int = Field(ge=0)


class MediaReviewIssueContribution(AipContractModel):
    issue_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)
    status: str = Field(min_length=1, max_length=80)
    severity: str = Field(min_length=1, max_length=80)
    artifact_id: str = Field(min_length=1, max_length=200)
    artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    return_stage: str = Field(min_length=1, max_length=160)
    return_decision_count: int = Field(ge=0)


class MediaCommandCapability(AipContractModel):
    command_id: str = Field(min_length=1, max_length=120)
    allowed: Literal[False] = False
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    expected_version: int | None = Field(default=None, ge=1)
    required_exact_refs: list[MediaLifecycleAuthorityRef] = Field(default_factory=list, max_length=20)


class MediaStudioLifecycleContribution(AipContractModel):
    schema_version: Literal[MEDIA_STUDIO_LIFECYCLE_SCHEMA_VERSION] = MEDIA_STUDIO_LIFECYCLE_SCHEMA_VERSION
    context_id: str = Field(min_length=1, max_length=200)
    context_revision: int = Field(ge=1)
    context_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_id: str = Field(min_length=1, max_length=200)
    status: Literal["ready", "partial", "blocked", "conflict"]
    lifecycle: list[MediaLifecycleNodeContribution] = Field(min_length=7, max_length=7)
    responsibilities: list[MediaResponsibilityContribution] = Field(min_length=8, max_length=8)
    stages: list[MediaStageContribution] = Field(default_factory=list, max_length=100)
    artifact_families: list[MediaArtifactFamilyContribution] = Field(default_factory=list, max_length=100)
    review_issues: list[MediaReviewIssueContribution] = Field(default_factory=list, max_length=100)
    command_capabilities: list[MediaCommandCapability] = Field(min_length=5, max_length=20)
    blocker_codes: list[str] = Field(default_factory=list, max_length=80)
    external_effects_allowed: Literal[False] = False

    @model_validator(mode="after")
    def _canonical_shape(self) -> "MediaStudioLifecycleContribution":
        if [item.node_id for item in self.lifecycle] != list(MediaLifecycleNodeId):
            raise ValueError("media lifecycle requires canonical seven-node order")
        expected_slots = list(MEDIA_RESPONSIBILITY_CAPABILITY_MAP)
        if [item.slot_id for item in self.responsibilities] != expected_slots:
            raise ValueError("media lifecycle requires canonical eight-slot order")
        if self.status == "ready" and self.blocker_codes:
            raise ValueError("ready lifecycle cannot contain blockers")
        if self.status in {"blocked", "conflict"} and not self.blocker_codes:
            raise ValueError("blocked or conflict lifecycle requires blockers")
        if len({(item.stage_id, item.task_run_id, item.attempt) for item in self.stages}) != len(self.stages):
            raise ValueError("media stages must be unique by stage/run/attempt")
        if len({item.family_id for item in self.artifact_families}) != len(self.artifact_families):
            raise ValueError("media artifact families must be unique")
        if len({(item.issue_id, item.version) for item in self.review_issues}) != len(self.review_issues):
            raise ValueError("media review issues must be unique by version")
        if len({item.command_id for item in self.command_capabilities}) != len(self.command_capabilities):
            raise ValueError("media command capabilities must be unique")
        return self


__all__ = [name for name in globals() if name.startswith("MEDIA_STUDIO") or name.startswith("Media")]
