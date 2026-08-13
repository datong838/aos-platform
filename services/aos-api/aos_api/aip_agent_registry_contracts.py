"""AIP-6 canonical contracts for agents, skills, bindings and handoffs.

This module freezes DTOs only. It never allocates a store, registers a route,
or turns the legacy in-memory agent engines into an authority.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, ResourceRef

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
