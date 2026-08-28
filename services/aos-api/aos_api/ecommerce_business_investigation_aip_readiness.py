"""Governed exact Binding readiness refresh for BI-W10 composition."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field

from aos_api.aip_agent_registry_contracts import EvaluateOperationalBindingRequest
from aos_api.aip_capability_binding_service import AipCapabilityBindingService
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import BriefLifecycle, ContractReadiness
from aos_api.aip_responsibility_template_authority import (
    resolve_responsibility_template,
)
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.aip_stage_template_authority import resolve_stage_template_source
from aos_api.ecommerce_business_investigation_aip_authority import (
    BusinessInvestigationAuthorityMaterializer,
    selected_skill_refs,
)
from aos_api.ecommerce_business_investigation_aip_composition import (
    INVESTIGATION_RESPONSIBILITY_PROFILE,
)
from aos_api.tenant_scope import TenantScope


class BindingRefreshObservation(AipContractModel):
    kind: Literal["capability", "skill"]
    binding_id: str
    before_version: int
    after_version: int
    disposition: Literal["evaluated", "fresh-skip"]
    readiness: str
    reasons: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class InvestigationBindingRefreshResult(AipContractModel):
    schema_version: str = "aos.ecommerce.business-investigation-binding-refresh/v1"
    tenant: TenantContext
    evaluated_at: datetime
    items: list[BindingRefreshObservation]
    responsibility_plan_id: str
    responsibility_plan_revision: int
    responsibility_plan_lifecycle: str
    responsibility_plan_readiness: str
    responsibility_plan_blockers: list[str] = Field(default_factory=list)


class BusinessInvestigationBindingReadinessCoordinator:
    """Refresh only the exact dependencies consumed by the BI responsibility plan."""

    def __init__(
        self,
        *,
        store: AipProductionContractStore | None = None,
        capabilities: AipCapabilityBindingService | None = None,
        skills: AipSkillRegistry | None = None,
        materializer: BusinessInvestigationAuthorityMaterializer | None = None,
        clock=None,
    ) -> None:
        self._store = store or AipProductionContractStore(
            responsibility_template_resolver=resolve_responsibility_template,
            stage_template_source_resolver=resolve_stage_template_source,
        )
        self._capabilities = capabilities or AipCapabilityBindingService()
        self._skills = skills or AipSkillRegistry()
        self._materializer = materializer or BusinessInvestigationAuthorityMaterializer(
            store=self._store
        )
        self._clock = clock or (lambda: datetime.now(UTC))

    def refresh(
        self,
        scope: TenantScope,
        *,
        actor: str = "aos-main-development",
        idempotency_prefix: str = "bi-w10-02-investigation-readiness",
    ) -> InvestigationBindingRefreshResult:
        now = self._clock()
        plan = self._current_plan(scope)
        assignee_ids = {
            slot.assignee.resource_id
            for slot in plan.slots
            if slot.assignee.kind.value == "agent_instance"
        }
        active_skills = [
            item
            for item in self._skills.list_bindings(scope, limit=200)
            if item.status == "active" and item.instance_id in assignee_ids
        ]
        capability_ids = sorted(
            {
                binding_id
                for item in active_skills
                for binding_id in item.capability_binding_ids
            }
        )
        observations = [
            self._refresh_capability(
                scope,
                binding_id,
                now=now,
                actor=actor,
                idempotency_prefix=idempotency_prefix,
            )
            for binding_id in capability_ids
        ]

        selected = selected_skill_refs()
        refreshed_skills = self._skills.list_bindings(scope, limit=200)
        for skill_id, exact in selected.items():
            candidates = [
                item
                for item in refreshed_skills
                if item.status == "active"
                and item.skill.asset_id == skill_id
                and item.skill.revision == exact.revision
                and item.skill.content_hash.removeprefix("sha256:")
                == exact.content_hash.removeprefix("sha256:")
            ]
            if len(candidates) != 1:
                raise ValueError(f"exact active SkillBinding unavailable: {skill_id}")
            observations.append(
                self._refresh_skill(
                    scope,
                    candidates[0],
                    now=now,
                    actor=actor,
                    idempotency_prefix=idempotency_prefix,
                )
            )

        plan = self._materializer.finalize_responsibility_plan(
            scope, plan.plan_id, actor=actor
        )
        return InvestigationBindingRefreshResult(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            evaluatedAt=now,
            items=observations,
            responsibilityPlanId=plan.plan_id,
            responsibilityPlanRevision=plan.revision,
            responsibilityPlanLifecycle=plan.lifecycle.value,
            responsibilityPlanReadiness=plan.readiness.value,
            responsibilityPlanBlockers=sorted(
                {blocker.code for blocker in plan.blockers}
            ),
        )

    def _current_plan(self, scope: TenantScope):
        plans = [
            item
            for item in self._store.list_responsibility_plans(scope).items
            if item.profile == INVESTIGATION_RESPONSIBILITY_PROFILE
            and item.lifecycle in {BriefLifecycle.DRAFT, BriefLifecycle.FROZEN}
        ]
        if len(plans) != 1:
            raise ValueError("unique BI responsibility plan unavailable")
        return plans[0]

    def _refresh_capability(
        self,
        scope: TenantScope,
        binding_id: str,
        *,
        now: datetime,
        actor: str,
        idempotency_prefix: str,
    ) -> BindingRefreshObservation:
        before = self._capabilities.get(scope, binding_id)
        if self._fresh(before, now):
            return self._observation("capability", before, before, "fresh-skip")
        after, readiness, _ = self._capabilities.evaluate(
            scope,
            binding_id,
            EvaluateOperationalBindingRequest(
                expectedVersion=before.version,
                dependencies=before.dependencies,
            ),
            idempotency_key=(
                f"{idempotency_prefix}:capability:{binding_id}:v{before.version}"
            ),
            actor=actor,
            evaluated_at=now,
        )
        return BindingRefreshObservation(
            kind="capability",
            bindingId=binding_id,
            beforeVersion=before.version,
            afterVersion=after.version,
            disposition="evaluated",
            readiness=readiness.readiness.value,
            reasons=readiness.reasons,
            expiresAt=readiness.expires_at,
        )

    def _refresh_skill(
        self,
        scope: TenantScope,
        before,
        *,
        now: datetime,
        actor: str,
        idempotency_prefix: str,
    ) -> BindingRefreshObservation:
        if self._fresh(before, now):
            return self._observation("skill", before, before, "fresh-skip")
        after, readiness, _ = self._skills.evaluate_binding(
            scope,
            before.binding_id,
            EvaluateOperationalBindingRequest(
                expectedVersion=before.version,
                dependencies=before.dependencies,
            ),
            idempotency_key=(
                f"{idempotency_prefix}:skill:{before.binding_id}:v{before.version}"
            ),
            actor=actor,
            evaluated_at=now,
        )
        return BindingRefreshObservation(
            kind="skill",
            bindingId=before.binding_id,
            beforeVersion=before.version,
            afterVersion=after.version,
            disposition="evaluated",
            readiness=readiness.readiness.value,
            reasons=readiness.reasons,
            expiresAt=readiness.expires_at,
        )

    @staticmethod
    def _fresh(item, now: datetime) -> bool:
        return bool(
            item.dependency_snapshot_hash
            and item.readiness_expires_at
            and item.readiness_expires_at > now
        )

    @staticmethod
    def _observation(kind, before, after, disposition):
        readiness = getattr(after, "operational_readiness", None) or getattr(
            after, "readiness", "blocked"
        )
        reasons = getattr(after, "readiness_reasons", [])
        return BindingRefreshObservation(
            kind=kind,
            bindingId=before.binding_id,
            beforeVersion=before.version,
            afterVersion=after.version,
            disposition=disposition,
            readiness=getattr(readiness, "value", readiness),
            reasons=list(reasons),
            expiresAt=after.readiness_expires_at,
        )
