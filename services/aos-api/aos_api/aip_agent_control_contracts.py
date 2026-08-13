"""AIP-6 A6F read models for canonical agent control plane."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from aos_api.aip_agent_registry_contracts import (
    AgentInstance,
    AgentTemplateRevision,
    CapabilityRevision,
    RegistryReceipt,
    SkillTemplateRevision,
)
from aos_api.aip_contracts import AipContractModel, TenantContext


class AgentCatalogItem(AipContractModel):
    template: AgentTemplateRevision
    instance: AgentInstance | None = None
    skills: list[SkillTemplateRevision] = Field(default_factory=list)
    required_capability_ids: list[str] = Field(default_factory=list)
    runtime_readiness: Literal["blocked"] = "blocked"
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


class AgentInstanceListResponse(AipContractModel):
    tenant: TenantContext
    items: list[AgentInstance]
    count: int = Field(ge=0)


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
    solution_pack_version: Literal["1.2.0"]
    status: Literal["installed", "partial"]
    items: list[AgentInstallItem]
    created_count: int = Field(ge=0)
    existing_count: int = Field(ge=0)
    runnable_count: Literal[0] = 0
