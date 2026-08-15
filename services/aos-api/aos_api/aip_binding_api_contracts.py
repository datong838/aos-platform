"""Strict canonical API contracts for tenant operational bindings."""
from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from aos_api.aip_agent_registry_contracts import (
    BindingHealth,
    CapabilityBinding,
    OperationalBindingDependencies,
    OperationalBindingReadiness,
    RegistryReceipt,
    SkillBinding,
    VersionedAssetRef,
)
from aos_api.aip_contracts import AipContractModel, TenantContext


class CapabilityBindingListResponse(AipContractModel):
    tenant: TenantContext
    items: list[CapabilityBinding]
    count: int = Field(ge=0)


class SkillBindingListResponse(AipContractModel):
    tenant: TenantContext
    items: list[SkillBinding]
    count: int = Field(ge=0)


class CapabilityBindingCommandResponse(AipContractModel):
    tenant: TenantContext
    binding: CapabilityBinding
    readiness: OperationalBindingReadiness | None = None
    receipt: RegistryReceipt


class SkillBindingCommandResponse(AipContractModel):
    tenant: TenantContext
    binding: SkillBinding
    readiness: OperationalBindingReadiness | None = None
    receipt: RegistryReceipt


class BindingReadinessResponse(AipContractModel):
    tenant: TenantContext
    readiness: OperationalBindingReadiness


class CapabilityBindingPreviewRequest(AipContractModel):
    capability: VersionedAssetRef
    dependencies: OperationalBindingDependencies

    @model_validator(mode="after")
    def _capability_kind(self) -> CapabilityBindingPreviewRequest:
        if self.capability.asset_type != "CapabilityRevision":
            raise ValueError("capability must reference CapabilityRevision")
        return self


class SkillBindingPreviewRequest(AipContractModel):
    instance_id: str = Field(min_length=1, max_length=200)
    skill: VersionedAssetRef
    capability_binding_ids: list[str] = Field(default_factory=list, max_length=128)
    budget_policy_ref: VersionedAssetRef
    dependencies: OperationalBindingDependencies

    @model_validator(mode="after")
    def _exact_kinds_and_budget(self) -> SkillBindingPreviewRequest:
        if self.skill.asset_type != "SkillTemplate":
            raise ValueError("skill must reference SkillTemplate")
        if self.budget_policy_ref.asset_type != "BudgetPolicyRevision":
            raise ValueError("budget_policy_ref must reference BudgetPolicyRevision")
        if self.dependencies.budget_policy_ref != self.budget_policy_ref:
            raise ValueError("dependencies budget policy must match binding budget policy")
        cleaned = [value.strip() for value in self.capability_binding_ids]
        if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("capability binding ids must be unique and non-blank")
        self.capability_binding_ids = cleaned
        return self


class CapabilityBindingTransitionRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    expected_dependency_snapshot_hash: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    health: BindingHealth
    observed_at: datetime


class SkillBindingTransitionRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    expected_dependency_snapshot_hash: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    occurred_at: datetime
