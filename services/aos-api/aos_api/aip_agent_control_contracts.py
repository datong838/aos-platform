"""AIP-6 A6F read models for canonical agent control plane."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from aos_api.aip_agent_registry_contracts import (
    AgentInstance,
    AgentTemplateRevision,
    CapabilityBinding,
    CapabilityRevision,
    RegistryReceipt,
    SkillBinding,
    SkillTemplateRevision,
)
from aos_api.aip_contracts import AipContractModel, TenantContext


class AgentCatalogItem(AipContractModel):
    template: AgentTemplateRevision
    instance: AgentInstance | None = None
    skills: list[SkillTemplateRevision] = Field(default_factory=list)
    required_capability_ids: list[str] = Field(default_factory=list)
    runtime_readiness: Literal["blocked", "runnable"] = "blocked"
    blockers: list[str] = Field(default_factory=list)


class AgentCatalogStats(AipContractModel):
    definition_count: int = Field(ge=0)
    installed_count: int = Field(ge=0)
    runnable_count: int = Field(ge=0)
    skill_definition_count: int = Field(ge=0)
    capability_definition_count: int = Field(ge=0)


class AgentCatalogResponse(AipContractModel):
    tenant: TenantContext
    items: list[AgentCatalogItem]
    stats: AgentCatalogStats


class AgentRuntimeBindingStats(AipContractModel):
    capability_binding_count: int = Field(ge=0)
    skill_binding_count: int = Field(ge=0)
    active_capability_binding_count: int = Field(ge=0)
    active_skill_binding_count: int = Field(ge=0)


class AgentRuntimeReadinessResponse(AipContractModel):
    tenant: TenantContext
    catalog: AgentCatalogResponse
    capability_bindings: list[CapabilityBinding]
    skill_bindings: list[SkillBinding]
    binding_stats: AgentRuntimeBindingStats
    evaluated_at: datetime


class OperationalStageCounts(AipContractModel):
    """Shared four-stage vocabulary used by every AIP operational surface."""

    definition: int = Field(ge=0)
    bound: int = Field(ge=0)
    enabled: int = Field(ge=0)
    runnable: int = Field(ge=0)

    @model_validator(mode="after")
    def _monotonic(self) -> "OperationalStageCounts":
        if not self.runnable <= self.enabled <= self.bound <= self.definition:
            raise ValueError("operational stage counts must be monotonic")
        return self


class OperationalProjectionSources(AipContractModel):
    agent_readiness_at: datetime
    model_runtime_at: datetime


class AipOperationalProjectionResponse(AipContractModel):
    """Read-only aggregate; canonical write ownership remains with source stores."""

    tenant: TenantContext
    roles: OperationalStageCounts
    capabilities: OperationalStageCounts
    tools: OperationalStageCounts
    eval_gates: OperationalStageCounts
    routes: OperationalStageCounts
    overall_readiness: Literal["ready", "blocked"]
    blocker_codes: list[str] = Field(default_factory=list)
    sources: OperationalProjectionSources
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: datetime

    @model_validator(mode="after")
    def _readiness_matches_blockers(self) -> "AipOperationalProjectionResponse":
        if self.overall_readiness == "ready" and self.blocker_codes:
            raise ValueError("ready projection must not contain blocker codes")
        if self.overall_readiness == "blocked" and not self.blocker_codes:
            raise ValueError("blocked projection requires blocker codes")
        return self


class AgentInstanceListResponse(AipContractModel):
    tenant: TenantContext
    items: list[AgentInstance]
    count: int = Field(ge=0)


class ActivateAgentInstanceRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    capability_binding_ids: list[str] = Field(min_length=1, max_length=128)


class AgentInstanceActivationResponse(AipContractModel):
    tenant: TenantContext
    instance: AgentInstance
    capability_binding_ids: list[str]
    receipt: RegistryReceipt


class CapabilityCatalogResponse(AipContractModel):
    tenant: TenantContext
    items: list[CapabilityRevision]
    count: int = Field(ge=0)
    available_count: int = Field(ge=0)


class AgentInstallItem(AipContractModel):
    instance: AgentInstance
    disposition: Literal["created", "existing"]
    receipt: RegistryReceipt | None = None


class AgentInstallResponse(AipContractModel):
    tenant: TenantContext
    solution_pack_id: Literal["solution.ecommerce.growth"]
    solution_pack_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    status: Literal["installed", "partial"]
    items: list[AgentInstallItem]
    created_count: int = Field(ge=0)
    existing_count: int = Field(ge=0)
    runnable_count: Literal[0] = 0
