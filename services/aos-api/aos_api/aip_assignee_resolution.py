"""Four-kind AssigneeResolutionReceipt (W-L20).

Never treats a tenant-global catalog hit as a resolved Tool/Provider binding.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_production_contracts import AssigneeKind, AssigneeRef


class AssigneeResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    BLOCKED = "blocked"


class AssigneeCandidateDecision(AipContractModel):
    assignee: AssigneeRef
    status: AssigneeResolutionStatus
    blocker_codes: list[str] = Field(default_factory=list)
    resolved_ref: str | None = None
    binding_refs: list[VersionedAssetRef] = Field(default_factory=list)


class ResolveAssigneeRequest(AipContractModel):
    assignee: AssigneeRef | None = None
    candidates: list[AssigneeRef] = Field(default_factory=list, max_length=128)
    subject_id: str = Field(min_length=1, max_length=240)
    required_capabilities: list[VersionedAssetRef] = Field(
        default_factory=list, max_length=128
    )
    policy_refs: list[VersionedAssetRef] = Field(default_factory=list, max_length=64)
    require_instance_scope: bool = True
    freshness_seconds: int = Field(default=300, ge=30, le=3600)

    @model_validator(mode="after")
    def _canonical_candidates(self) -> ResolveAssigneeRequest:
        values = ([self.assignee] if self.assignee is not None else []) + self.candidates
        if not values:
            raise ValueError("assignee or candidates is required")
        identities = [
            (item.kind.value, item.resource_id, item.version) for item in values
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("assignee candidates must be unique exact refs")
        required = [
            (item.asset_type, item.asset_id, item.revision, item.content_hash)
            for item in self.required_capabilities
        ]
        if any(item.asset_type != "CapabilityRevision" for item in self.required_capabilities):
            raise ValueError("required capabilities must reference CapabilityRevision")
        if len(required) != len(set(required)):
            raise ValueError("required capabilities must be unique exact refs")
        policies = [
            (item.asset_type, item.asset_id, item.revision, item.content_hash)
            for item in self.policy_refs
        ]
        if len(policies) != len(set(policies)):
            raise ValueError("policy refs must be unique exact refs")
        return self

    @property
    def canonical_candidates(self) -> list[AssigneeRef]:
        values = ([self.assignee] if self.assignee is not None else []) + self.candidates
        return sorted(
            values,
            key=lambda item: (item.kind.value, item.resource_id, item.version),
        )


class AssigneeResolutionReceipt(AipContractModel):
    tenant: TenantContext
    receipt_id: str
    subject_id: str
    kind: AssigneeKind
    resource_id: str
    version: int = Field(ge=1)
    status: AssigneeResolutionStatus
    resolved_ref: str | None = None
    blocker_codes: list[str] = Field(default_factory=list)
    actor: str
    created_at: datetime
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_assignee: AssigneeRef | None = None
    required_capabilities: list[VersionedAssetRef] = Field(default_factory=list)
    candidate_decisions: list[AssigneeCandidateDecision] = Field(default_factory=list)
    binding_refs: list[VersionedAssetRef] = Field(default_factory=list)
    policy_refs: list[VersionedAssetRef] = Field(default_factory=list)
    snapshot_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    expires_at: datetime | None = None


class UpsertToolBindingRequest(AipContractModel):
    binding_id: str = Field(min_length=1, max_length=200)
    tool_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)
    agent_instance_id: str = Field(min_length=1, max_length=200)
    status: str = Field(default="active", pattern=r"^(active|disabled)$")
    capability_binding_ids: list[str] = Field(default_factory=list, max_length=128)
    policy_refs: list[VersionedAssetRef] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def _binding_inputs_are_unique(self) -> UpsertToolBindingRequest:
        if len(self.capability_binding_ids) != len(set(self.capability_binding_ids)):
            raise ValueError("capability binding ids must be unique")
        policy_keys = [
            (item.asset_type, item.asset_id, item.revision, item.content_hash)
            for item in self.policy_refs
        ]
        if len(policy_keys) != len(set(policy_keys)):
            raise ValueError("policy refs must be unique exact refs")
        return self


class ToolBindingRecord(AipContractModel):
    tenant: TenantContext
    binding_id: str
    tool_id: str
    version: int
    agent_instance_id: str
    status: str
    capability_binding_ids: list[str] = Field(default_factory=list)
    policy_refs: list[VersionedAssetRef] = Field(default_factory=list)


__all__ = [
    "AssigneeCandidateDecision",
    "AssigneeResolutionReceipt",
    "AssigneeResolutionStatus",
    "ResolveAssigneeRequest",
    "ToolBindingRecord",
    "UpsertToolBindingRequest",
]
