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
    AgentInstanceStatus,
    CapabilityReadiness,
    CreateAgentInstanceRequest,
    EvaluateOperationalBindingRequest,
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
from aos_api.aip_solution_pack_publisher import (
    AIP_DEFINITION_SOURCE_VERSION,
    AGENT_LOGIC_COUNTS,
    CAPABILITY_IDS,
    LOGIC_IDS,
    SOLUTION_PACK_ID,
    SOLUTION_PACK_VERSION,
)
from aos_api.auth import Principal
from aos_api.tenant_scope import TenantScope

class AipEcommerceCatalogInvalid(AipAgentRegistryConflict):
    code = "AIP_ECOMMERCE_CATALOG_INVALID"


def _value(item: object) -> str:
    if item is None:
        return ""
    return str(getattr(item, "value", item))


def _fresh_available(status: object, readiness: object, expires_at: object, now: datetime) -> bool:
    return (
        _value(status) == "active"
        and _value(readiness) == "available"
        and expires_at is not None
        and expires_at > now
    )


def compute_catalog_item_runtime(
    *,
    instance: object | None,
    role_skills: list[object],
    skill_bindings: list[object],
    capability_bindings: list[object],
    now: datetime,
) -> tuple[str, list[str]]:
    """Compute live catalog readiness. Template.manifest blockers are definition placeholders."""
    blockers: list[str] = []
    instance_active = instance is not None and _value(getattr(instance, "status", None)) == "active"
    if instance is None:
        blockers.append("agent_instance_not_installed")
    elif not instance_active:
        blockers.append("agent_instance_not_active")

    published_skills = [
        skill for skill in role_skills if _value(getattr(skill, "lifecycle", None)) == "published"
    ]
    all_skills_published = bool(role_skills) and len(published_skills) == len(role_skills)
    if not all_skills_published:
        blockers.append("skill_templates_not_published")

    instance_id = getattr(instance, "instance_id", None) if instance is not None else None
    all_skills_fresh = all_skills_published
    stale_skill = False
    unavailable_skill = False
    for skill in published_skills:
        exact_bindings = []
        for binding in skill_bindings:
            if instance_id and getattr(binding, "instance_id", None) != instance_id:
                continue
            skill_ref = getattr(binding, "skill", None)
            if (
                getattr(skill_ref, "asset_id", None) == getattr(skill, "skill_id", None)
                and getattr(skill_ref, "revision", None) == getattr(skill, "revision", None)
            ):
                exact_bindings.append(binding)
        if any(
            _fresh_available(
                getattr(binding, "status", None),
                getattr(binding, "readiness", None),
                getattr(binding, "readiness_expires_at", None),
                now,
            )
            for binding in exact_bindings
        ):
            continue
        all_skills_fresh = False
        if any(_value(getattr(binding, "status", None)) == "active" for binding in exact_bindings):
            stale_skill = True
        else:
            unavailable_skill = True
    if stale_skill:
        blockers.append("skill_binding_readiness_stale")
    if unavailable_skill or not published_skills:
        blockers.append("skill_binding_unavailable")

    required = {
        cap
        for skill in role_skills
        for cap in getattr(skill, "required_capabilities", [])
    }
    all_capabilities_fresh = bool(required)
    stale_cap = False
    unavailable_cap = False
    for capability_id in required:
        matching = [
            binding
            for binding in capability_bindings
            if getattr(getattr(binding, "capability", None), "asset_id", None) == capability_id
        ]
        if any(
            _fresh_available(
                getattr(binding, "status", None),
                getattr(binding, "operational_readiness", None),
                getattr(binding, "readiness_expires_at", None),
                now,
            )
            for binding in matching
        ):
            continue
        all_capabilities_fresh = False
        if any(_value(getattr(binding, "status", None)) == "active" for binding in matching):
            stale_cap = True
        else:
            unavailable_cap = True
    if stale_cap:
        blockers.append("capability_binding_readiness_stale")
    if unavailable_cap or not required:
        blockers.append("capability_bindings_unavailable")

    blockers = sorted(set(blockers))
    if instance_active and all_skills_fresh and all_capabilities_fresh:
        return "runnable", []
    return "blocked", blockers


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

    def _definitions(self, principal: Principal):
        templates = self._agents.list_templates(
            source_resource_id=SOLUTION_PACK_ID,
            source_revision=AIP_DEFINITION_SOURCE_VERSION,
            lifecycle=TemplateLifecycle.PUBLISHED,
        )
        skills = self._skills.list_skills(
            source_resource_id=SOLUTION_PACK_ID,
            source_revision=AIP_DEFINITION_SOURCE_VERSION,
            limit=200,
        )
        capabilities = self._capabilities.list_capabilities(
            source_resource_id=SOLUTION_PACK_ID,
            source_revision=AIP_DEFINITION_SOURCE_VERSION,
            lifecycle=TemplateLifecycle.PUBLISHED,
        )
        expected_skill_ids = {f"ecommerce.skill.{logic_id}" for logic_id in LOGIC_IDS}
        latest_templates = self._latest(
            [item for item in templates if item.template_id in AGENT_LOGIC_COUNTS],
            "template_id",
        )
        # Published Skill revisions are tenant-scoped authority.  Another
        # tenant may discover the global evaluated definition, but must never
        # receive a revision carrying a foreign publicationTenant.
        eligible_skills = [
            item
            for item in skills
            if item.skill_id in expected_skill_ids
            and (
                item.publication_tenant is None
                or (
                    item.publication_tenant.org_id == principal.org_id
                    and item.publication_tenant.project_id == principal.project_id
                )
            )
        ]
        latest_skills = self._latest(
            eligible_skills,
            "skill_id",
        )
        latest_capabilities = self._latest(
            [item for item in capabilities if item.capability_id in CAPABILITY_IDS],
            "capability_id",
        )
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
        templates, skills, capabilities = self._definitions(principal)
        scope = self._scope(principal)
        now = self._clock()
        instances = {item.template.asset_id: item for item in self._agents.list_instances(scope)}
        skill_bindings = self._skills.list_bindings(scope, limit=200)
        capability_bindings = self._capability_bindings.list_bindings(scope, limit=200)
        skills_by_logic = {item.canonical_logic_id.removeprefix("ecommerce.logic."): item for item in skills.values()}
        items = []
        runnable_count = 0
        for template_id in sorted(templates):
            template = templates[template_id]
            instance = instances.get(template_id)
            logic_ids = template.manifest.get("logicIds", [])
            role_skills = [skills_by_logic[logic_id] for logic_id in logic_ids if logic_id in skills_by_logic]
            if len(role_skills) != AGENT_LOGIC_COUNTS[template_id]:
                raise AipEcommerceCatalogInvalid(f"skill crosswalk incomplete for {template_id}")
            required = sorted({cap for skill in role_skills for cap in skill.required_capabilities})
            readiness, blockers = compute_catalog_item_runtime(
                instance=instance,
                role_skills=role_skills,
                skill_bindings=skill_bindings,
                capability_bindings=capability_bindings,
                now=now,
            )
            if readiness == "runnable":
                runnable_count += 1
            items.append(AgentCatalogItem(
                template=template,
                instance=instance,
                skills=role_skills,
                required_capability_ids=required,
                runtime_readiness=readiness,
                blockers=blockers,
            ))
        return AgentCatalogResponse(
            tenant=self._tenant(principal),
            items=items,
            stats=AgentCatalogStats(
                definition_count=len(items),
                installed_count=sum(item.instance is not None for item in items),
                runnable_count=runnable_count,
                skill_definition_count=len(skills),
                capability_definition_count=len(capabilities),
            ),
        )

    def capability_catalog(self, principal: Principal) -> CapabilityCatalogResponse:
        _, _, capabilities = self._definitions(principal)
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

    def refresh_binding_readiness(
        self,
        principal: Principal,
        *,
        idempotency_key: str,
    ) -> AgentRuntimeReadinessResponse:
        """Re-evaluate stale/unavailable active Bindings, then return live catalog projection.

        Soft-fail per binding: multimedia Health gaps must not abort text Pilot refresh.
        """
        scope = self._scope(principal)
        now = self._clock()
        actor = principal.subject or "aip-catalog-refresh"

        for binding in self._capability_bindings.list_bindings(scope, limit=200):
            if _value(getattr(binding, "status", None)) != "active":
                continue
            if _fresh_available(
                binding.status,
                getattr(binding, "operational_readiness", None),
                getattr(binding, "readiness_expires_at", None),
                now,
            ):
                continue
            try:
                self._capability_bindings.evaluate(
                    scope,
                    binding.binding_id,
                    EvaluateOperationalBindingRequest(
                        expected_version=binding.version,
                        dependencies=binding.dependencies,
                    ),
                    idempotency_key=(
                        f"{idempotency_key}:capability:{binding.binding_id}"
                    ),
                    actor=actor,
                    evaluated_at=now,
                )
            except Exception:
                continue

        for binding in self._skills.list_bindings(scope, limit=200):
            if _value(getattr(binding, "status", None)) != "active":
                continue
            if _fresh_available(
                binding.status,
                getattr(binding, "readiness", None),
                getattr(binding, "readiness_expires_at", None),
                now,
            ):
                continue
            try:
                self._skills.evaluate_binding(
                    scope,
                    binding.binding_id,
                    EvaluateOperationalBindingRequest(
                        expected_version=binding.version,
                        dependencies=binding.dependencies,
                    ),
                    idempotency_key=f"{idempotency_key}:skill:{binding.binding_id}",
                    actor=actor,
                    evaluated_at=now,
                )
            except Exception:
                continue

        return self.runtime_readiness(principal)

    def install(self, principal: Principal, *, idempotency_key: str) -> AgentInstallResponse:
        templates, _, _ = self._definitions(principal)
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
