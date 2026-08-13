"""AIP-6 canonical contracts for agents, skills, bindings and handoffs.

This module freezes DTOs only. It never allocates a store, registers a route,
or turns the legacy in-memory agent engines into an authority.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, ResourceRef, TenantContext

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class TemplateLifecycle(StrEnum):
    DRAFT = "draft"
    EVALUATED = "evaluated"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    REVOKED = "revoked"


class AgentInstanceStatus(StrEnum):
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class BindingHealth(StrEnum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    REVOKED = "revoked"


class CapabilityReadiness(StrEnum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class AgentRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class VersionedAssetRef(AipContractModel):
    asset_type: str = Field(min_length=1, max_length=80)
    asset_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=SHA256_PATTERN)

    @field_validator("asset_type", "asset_id")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("asset reference fields must not be blank")
        return cleaned


class AgentInstanceOverlay(AipContractModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    prompt_revision: str | None = Field(default=None, min_length=1, max_length=120)
    allowed_capability_ids: list[str] = Field(default_factory=list, max_length=128)
    monthly_budget_minor: int | None = Field(default=None, ge=0)
    policy_revision: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("allowed_capability_ids")
    @classmethod
    def _unique_capabilities(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("allowed capability ids must be unique and non-blank")
        return cleaned


class CapabilityBindingRequest(AipContractModel):
    capability: VersionedAssetRef
    secret_ref: str = Field(min_length=1, max_length=512)
    network_policy_revision: str = Field(min_length=1, max_length=120)
    quota_policy_revision: str = Field(min_length=1, max_length=120)
    timeout_ms: int = Field(ge=100, le=3_600_000)
    max_concurrency: int = Field(ge=1, le=10_000)

    @field_validator("secret_ref")
    @classmethod
    def _secret_reference_only(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.startswith(("vault://", "secret://", "keychain://")):
            raise ValueError("secret_ref must be an opaque secret reference")
        return cleaned

    @model_validator(mode="after")
    def _capability_kind(self) -> CapabilityBindingRequest:
        if self.capability.asset_type != "CapabilityRevision":
            raise ValueError("capability must reference CapabilityRevision")
        return self


class HandoffEnvelopeRequest(AipContractModel):
    task_ref: ResourceRef
    run_ref: ResourceRef
    sender_instance: VersionedAssetRef
    receiver_instance: VersionedAssetRef
    object_refs: list[ResourceRef] = Field(default_factory=list, max_length=100)
    artifact_refs: list[ResourceRef] = Field(default_factory=list, max_length=100)
    evidence_refs: list[ResourceRef] = Field(default_factory=list, max_length=100)
    context: dict[str, Any] = Field(default_factory=dict)
    allowed_context_fields: list[str] = Field(default_factory=list, max_length=64)
    markings: list[str] = Field(min_length=1, max_length=32)
    expires_at: datetime

    @field_validator("allowed_context_fields", "markings")
    @classmethod
    def _unique_non_blank(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("allowlist and markings must be unique and non-blank")
        return cleaned

    @model_validator(mode="after")
    def _minimal_disclosure(self) -> HandoffEnvelopeRequest:
        allowed = set(self.allowed_context_fields)
        if set(self.context) - allowed:
            raise ValueError("handoff context contains fields outside the allowlist")
        if self.sender_instance.asset_id == self.receiver_instance.asset_id:
            raise ValueError("handoff sender and receiver must differ")
        return self


class AgentRunRequest(AipContractModel):
    task_ref: ResourceRef
    plan_ref: ResourceRef
    agent_instance: VersionedAssetRef
    skill: VersionedAssetRef
    logic: VersionedAssetRef
    model_route: VersionedAssetRef
    policy: VersionedAssetRef
    input_refs: list[ResourceRef] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def _asset_kinds(self) -> AgentRunRequest:
        expected = {
            "agent_instance": "AgentInstance",
            "skill": "SkillTemplate",
            "logic": "LogicRevision",
            "model_route": "ModelRouteRevision",
            "policy": "PolicyRevision",
        }
        for field_name, asset_type in expected.items():
            if getattr(self, field_name).asset_type != asset_type:
                raise ValueError(f"{field_name} must reference {asset_type}")
        return self


class PublishAgentTemplateRequest(AipContractModel):
    template_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    display_name: str = Field(min_length=1, max_length=120)
    role_key: str = Field(min_length=1, max_length=120)
    lifecycle: TemplateLifecycle
    source_ref: ResourceRef
    source_license: str = Field(min_length=1, max_length=200)
    manifest: dict[str, Any]
    content_hash: str = Field(pattern=SHA256_PATTERN)


class AgentTemplateRevision(PublishAgentTemplateRequest):
    created_by: str
    created_at: datetime


class PublishSkillTemplateRequest(AipContractModel):
    skill_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    canonical_logic_id: str = Field(min_length=1, max_length=200)
    lifecycle: TemplateLifecycle
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    tool_allowlist: list[str] = Field(default_factory=list, max_length=128)
    required_capabilities: list[str] = Field(default_factory=list, max_length=128)
    risk_level: str = Field(pattern=r"^(low|medium|high|critical)$")
    eval_pack_ref: VersionedAssetRef | None = None
    memory_policy_ref: VersionedAssetRef
    handoff_policy_ref: VersionedAssetRef
    source_ref: ResourceRef
    source_license: str = Field(min_length=1, max_length=200)
    content_hash: str = Field(pattern=SHA256_PATTERN)

    @field_validator("tool_allowlist", "required_capabilities")
    @classmethod
    def _unique_non_blank_assets(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("asset ids must be unique and non-blank")
        return cleaned


class SkillTemplateRevision(PublishSkillTemplateRequest):
    created_by: str
    created_at: datetime


class PublishCapabilityRevisionRequest(AipContractModel):
    capability_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    display_name: str = Field(min_length=1, max_length=120)
    lifecycle: TemplateLifecycle
    parent_ref: VersionedAssetRef | None = None
    aliases: list[str] = Field(default_factory=list, max_length=64)
    input_schema_ref: VersionedAssetRef
    output_schema_ref: VersionedAssetRef
    risk_level: str = Field(pattern=r"^(low|medium|high|critical)$")
    required_data_refs: list[VersionedAssetRef] = Field(default_factory=list, max_length=128)
    required_tool_refs: list[VersionedAssetRef] = Field(default_factory=list, max_length=128)
    required_capability_refs: list[VersionedAssetRef] = Field(default_factory=list, max_length=128)
    eval_pack_ref: VersionedAssetRef | None = None
    memory_policy_ref: VersionedAssetRef
    handoff_policy_ref: VersionedAssetRef
    effect_review_schema_ref: VersionedAssetRef
    license_policy_ref: VersionedAssetRef
    readiness_policy_ref: VersionedAssetRef
    readiness: CapabilityReadiness
    readiness_reasons: list[str] = Field(default_factory=list, max_length=64)
    source_ref: ResourceRef
    source_license: str = Field(min_length=1, max_length=200)
    content_hash: str = Field(pattern=SHA256_PATTERN)

    @field_validator("aliases", "readiness_reasons")
    @classmethod
    def _unique_non_blank_strings(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("aliases and readiness reasons must be unique and non-blank")
        return cleaned

    @model_validator(mode="after")
    def _capability_reference_kinds(self) -> PublishCapabilityRevisionRequest:
        if self.parent_ref and self.parent_ref.asset_type != "CapabilityRevision":
            raise ValueError("parent_ref must reference CapabilityRevision")
        if any(ref.asset_type != "CapabilityRevision" for ref in self.required_capability_refs):
            raise ValueError("required capability refs must reference CapabilityRevision")
        if self.capability_id in self.aliases:
            raise ValueError("canonical capability id cannot also be an alias")
        return self


class CapabilityRevision(PublishCapabilityRevisionRequest):
    created_by: str
    created_at: datetime


class CreateAgentInstanceRequest(AipContractModel):
    instance_id: str = Field(min_length=1, max_length=200)
    template: VersionedAssetRef
    overlay: AgentInstanceOverlay = Field(default_factory=AgentInstanceOverlay)
    initial_status: AgentInstanceStatus = AgentInstanceStatus.PROVISIONING

    @model_validator(mode="after")
    def _template_kind(self) -> CreateAgentInstanceRequest:
        if self.template.asset_type != "AgentTemplate":
            raise ValueError("template must reference AgentTemplate")
        return self


class UpdateAgentInstanceRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    from_status: AgentInstanceStatus
    to_status: AgentInstanceStatus
    overlay: AgentInstanceOverlay


class AgentInstance(AipContractModel):
    tenant: TenantContext
    instance_id: str
    instance_ref: VersionedAssetRef
    template: VersionedAssetRef
    status: AgentInstanceStatus
    overlay: AgentInstanceOverlay
    version: int = Field(ge=1)
    created_by: str
    created_at: datetime
    updated_at: datetime


class CreateSkillBindingRequest(AipContractModel):
    binding_id: str = Field(min_length=1, max_length=200)
    instance_id: str = Field(min_length=1, max_length=200)
    skill: VersionedAssetRef
    capability_binding_ids: list[str] = Field(default_factory=list, max_length=128)
    budget_policy_ref: VersionedAssetRef
    initial_status: str = Field(default="provisioning", pattern=r"^(provisioning|active|suspended|revoked)$")

    @model_validator(mode="after")
    def _skill_kind(self) -> CreateSkillBindingRequest:
        if self.skill.asset_type != "SkillTemplate":
            raise ValueError("skill must reference SkillTemplate")
        return self


class UpdateSkillBindingRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    from_status: str = Field(pattern=r"^(provisioning|active|suspended|revoked)$")
    to_status: str = Field(pattern=r"^(provisioning|active|suspended|revoked)$")


class SkillBinding(AipContractModel):
    tenant: TenantContext
    binding_id: str
    instance_id: str
    skill: VersionedAssetRef
    capability_binding_ids: list[str]
    budget_policy_ref: VersionedAssetRef
    status: str
    version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime


class RegistryReceipt(AipContractModel):
    tenant: TenantContext
    receipt_id: str
    operation: str
    idempotency_key: str
    request_hash: str = Field(pattern=SHA256_PATTERN)
    resource_ref: ResourceRef
    result_ref: ResourceRef
    status: str
    created_by: str
    created_at: datetime


class CreateCapabilityBindingRequest(AipContractModel):
    binding_id: str = Field(min_length=1, max_length=200)
    binding: CapabilityBindingRequest


class UpdateCapabilityBindingRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    from_status: str = Field(pattern=r"^(provisioning|active|suspended|revoked)$")
    to_status: str = Field(pattern=r"^(provisioning|active|suspended|revoked)$")
    health: BindingHealth
    observed_at: datetime


class CapabilityBinding(AipContractModel):
    tenant: TenantContext
    binding_id: str
    capability: VersionedAssetRef
    secret_ref: str
    health: BindingHealth
    network_policy_revision: str
    quota_policy_revision: str
    timeout_ms: int
    max_concurrency: int
    status: str
    version: int
    observed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CreateAgentRunRequest(AipContractModel):
    agent_run_id: str = Field(min_length=1, max_length=200)
    task_run_ref: ResourceRef
    skill_binding_id: str = Field(min_length=1, max_length=200)
    run: AgentRunRequest

    @model_validator(mode="after")
    def _task_run_kind(self) -> CreateAgentRunRequest:
        if self.task_run_ref.resource_type != "TaskRun":
            raise ValueError("task_run_ref must reference TaskRun")
        return self


class AgentRun(AipContractModel):
    tenant: TenantContext
    agent_run_id: str
    task_id: str
    task_run_id: str
    instance_id: str
    instance_version: int
    skill_binding_id: str
    request: AgentRunRequest
    status: AgentRunStatus
    version: int
    created_at: datetime
    updated_at: datetime


class IssueHandoffRequest(AipContractModel):
    handoff_id: str = Field(min_length=1, max_length=200)
    envelope: HandoffEnvelopeRequest


class HandoffEnvelope(AipContractModel):
    tenant: TenantContext
    handoff_id: str
    envelope: HandoffEnvelopeRequest
    status: str
    version: int
    consumed_at: datetime | None = None
    created_at: datetime


class IssuedHandoff(AipContractModel):
    handoff: HandoffEnvelope
    # The bearer is returned only on the first successful issue. An idempotent
    # replay can return the durable result but must never mint another token.
    bearer_token: str | None = Field(default=None, min_length=32)
    receipt: RegistryReceipt
