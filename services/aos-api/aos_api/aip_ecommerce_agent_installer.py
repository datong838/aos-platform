"""A6F tenant installer and canonical ecommerce agent catalog projection."""
from __future__ import annotations

from datetime import UTC, datetime

from aos_api.aip_agent_control_contracts import (
    AgentCatalogItem,
    AgentCatalogResponse,
    AgentCatalogStats,
    AgentInstallItem,
    AgentInstallResponse,
    AgentRuntimeBindingStats,
    AgentRuntimeReadinessResponse,
    CapabilityCatalogResponse,
)
from aos_api.aip_agent_registry_contracts import (
    AgentInstanceOverlay,
    CreateAgentInstanceRequest,
    TemplateLifecycle,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryNotFound,
    AipAgentRegistryStore,
)
from aos_api.aip_capability_registry import AipCapabilityRegistry
from aos_api.aip_capability_binding_service import AipCapabilityBindingService
from aos_api.aip_contracts import TenantContext
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.aip_solution_pack_publisher import AGENT_LOGIC_COUNTS, CAPABILITY_IDS
from aos_api.auth import Principal
from aos_api.tenant_scope import TenantScope

SOLUTION_PACK_ID = "solution.ecommerce.growth"
SOLUTION_PACK_VERSION = "1.2.0"


class AipEcommerceCatalogInvalid(AipAgentRegistryConflict):
    code = "AIP_ECOMMERCE_CATALOG_INVALID"


class AipEcommerceAgentInstaller:
    def __init__(
        self,
        *,
        agents: AipAgentRegistryStore | None = None,
        skills: AipSkillRegistry | None = None,
        capabilities: AipCapabilityRegistry | None = None,
        capability_bindings: AipCapabilityBindingService | None = None,
        clock=None,
    ) -> None:
        self._agents = agents or AipAgentRegistryStore()
        self._skills = skills or AipSkillRegistry()
        self._capabilities = capabilities or AipCapabilityRegistry()
        self._capability_bindings = capability_bindings or AipCapabilityBindingService()
        self._clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def _scope(principal: Principal) -> TenantScope:
        return TenantScope(principal.org_id, principal.project_id)

    @staticmethod
    def _tenant(principal: Principal) -> TenantContext:
        return TenantContext(org_id=principal.org_id, project_id=principal.project_id)

    def _definitions(self):
        templates = self._agents.list_templates(
            source_resource_id=SOLUTION_PACK_ID,
            source_revision=SOLUTION_PACK_VERSION,
            lifecycle=TemplateLifecycle.PUBLISHED,
        )
        skills = self._skills.list_skills(
            source_resource_id=SOLUTION_PACK_ID,
            source_revision=SOLUTION_PACK_VERSION,
            lifecycle=TemplateLifecycle.EVALUATED,
        )
        capabilities = self._capabilities.list_capabilities(
            source_resource_id=SOLUTION_PACK_ID,
            source_revision=SOLUTION_PACK_VERSION,
            lifecycle=TemplateLifecycle.PUBLISHED,
        )
        latest_templates = self._latest(templates, "template_id")
        latest_skills = self._latest(skills, "skill_id")
        latest_capabilities = self._latest(capabilities, "capability_id")
        if set(latest_templates) != set(AGENT_LOGIC_COUNTS):
            raise AipEcommerceCatalogInvalid("ecommerce agent definitions differ from 6-role authority")
        if len(latest_skills) != 37:
            raise AipEcommerceCatalogInvalid("ecommerce skill definitions differ from 37-logic authority")
        if tuple(sorted(latest_capabilities)) != tuple(sorted(CAPABILITY_IDS)):
            raise AipEcommerceCatalogInvalid("ecommerce capability definitions differ from 10-capability authority")
        return latest_templates, latest_skills, latest_capabilities

    @staticmethod
    def _latest(items, identity: str):
        result = {}
        for item in items:
            key = getattr(item, identity)
            if key not in result or item.revision > result[key].revision:
                result[key] = item
        return result

    def catalog(self, principal: Principal) -> AgentCatalogResponse:
        templates, skills, capabilities = self._definitions()
        instances = {item.template.asset_id: item for item in self._agents.list_instances(self._scope(principal))}
        skills_by_logic = {item.canonical_logic_id.removeprefix("ecommerce.logic."): item for item in skills.values()}
        items = []
        for template_id in sorted(templates):
            template = templates[template_id]
            logic_ids = template.manifest.get("logicIds", [])
            role_skills = [skills_by_logic[logic_id] for logic_id in logic_ids if logic_id in skills_by_logic]
            if len(role_skills) != AGENT_LOGIC_COUNTS[template_id]:
                raise AipEcommerceCatalogInvalid(f"skill crosswalk incomplete for {template_id}")
            required = sorted({cap for skill in role_skills for cap in skill.required_capabilities})
            blockers = sorted({*template.manifest.get("blockers", []), "skill_templates_not_published", "capability_bindings_unavailable", "model_route_unavailable"})
            items.append(AgentCatalogItem(
                template=template,
                instance=instances.get(template_id),
                skills=role_skills,
                required_capability_ids=required,
                blockers=blockers,
            ))
        return AgentCatalogResponse(
            tenant=self._tenant(principal),
            items=items,
            stats=AgentCatalogStats(
                definition_count=len(items),
                installed_count=sum(item.instance is not None for item in items),
                runnable_count=0,
                skill_definition_count=len(skills),
                capability_definition_count=len(capabilities),
            ),
        )

    def capability_catalog(self, principal: Principal) -> CapabilityCatalogResponse:
        _, _, capabilities = self._definitions()
        items = [capabilities[key] for key in sorted(capabilities)]
        return CapabilityCatalogResponse(
            tenant=self._tenant(principal),
            items=items,
            count=len(items),
            available_count=sum(item.readiness.value == "available" for item in items),
        )

    def runtime_readiness(self, principal: Principal) -> AgentRuntimeReadinessResponse:
        scope = self._scope(principal)
        catalog = self.catalog(principal)
        capability_bindings = self._capability_bindings.list_bindings(scope, limit=200)
        skill_bindings = self._skills.list_bindings(scope, limit=200)
        return AgentRuntimeReadinessResponse(
            tenant=self._tenant(principal),
            catalog=catalog,
            capability_bindings=capability_bindings,
            skill_bindings=skill_bindings,
            binding_stats=AgentRuntimeBindingStats(
                capability_binding_count=len(capability_bindings),
                skill_binding_count=len(skill_bindings),
                active_capability_binding_count=sum(
                    item.status == "active" for item in capability_bindings
                ),
                active_skill_binding_count=sum(
                    item.status == "active" for item in skill_bindings
                ),
            ),
            evaluated_at=self._clock(),
        )

    def install(self, principal: Principal, *, idempotency_key: str) -> AgentInstallResponse:
        templates, _, _ = self._definitions()
        scope = self._scope(principal)
        results = []
        for template_id in sorted(templates):
            template = templates[template_id]
            instance_id = f"{template_id}.default"
            request = CreateAgentInstanceRequest(
                instance_id=instance_id,
                template=VersionedAssetRef(
                    asset_type="AgentTemplate",
                    asset_id=template.template_id,
                    revision=template.revision,
                    content_hash=template.content_hash,
                ),
                overlay=AgentInstanceOverlay(display_name=template.display_name),
            )
            try:
                existing = self._agents.get_instance(scope, instance_id)
            except AipAgentRegistryNotFound:
                instance, receipt = self._agents.create_instance(
                    scope,
                    request,
                    idempotency_key=f"{idempotency_key}:{template_id}",
                    actor=principal.subject,
                    occurred_at=self._clock(),
                )
                results.append(AgentInstallItem(instance=instance, disposition="created", receipt=receipt))
                continue
            if existing.template != request.template or existing.overlay != request.overlay:
                raise AipEcommerceCatalogInvalid(f"existing agent instance drifted: {instance_id}")
            results.append(AgentInstallItem(instance=existing, disposition="existing"))
        return AgentInstallResponse(
            tenant=self._tenant(principal),
            solution_pack_id=SOLUTION_PACK_ID,
            solution_pack_version=SOLUTION_PACK_VERSION,
            status="installed" if len(results) == 6 else "partial",
            items=results,
            created_count=sum(item.disposition == "created" for item in results),
            existing_count=sum(item.disposition == "existing" for item in results),
        )
