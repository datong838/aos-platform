"""BI-W5-07 read-only composition of canonical Task Cockpit contributions."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import Field

from aos_api.aip_business_investigation_compiler import BusinessInvestigationCompilation
from aos_api.aip_business_investigation_runtime import BusinessInvestigationRuntimeBinding
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.ecommerce_workshop_task_cockpit_contracts import (
    TaskCockpitResponsibilityHandoffEnvelope,
    TaskCockpitSkillContributionEnvelope,
)
from aos_api.tenant_scope import TenantScope


class BusinessInvestigationContributionSideEffects(AipContractModel):
    agent_run_created_count: Literal[0] = 0
    handoff_created_count: Literal[0] = 0
    task_run_transition_count: Literal[0] = 0
    external_business_mutation_count: Literal[0] = 0


class BusinessInvestigationContributionView(AipContractModel):
    tenant: TenantContext
    task_id: str
    run_id: str
    responsibility_plan_ref: ExactRevisionRef
    skill_contributions: TaskCockpitSkillContributionEnvelope
    responsibility_handoffs: TaskCockpitResponsibilityHandoffEnvelope
    projection_status: Literal["ready", "blocked"]
    blocker_codes: list[str] = Field(default_factory=list, max_length=128)
    side_effects: BusinessInvestigationContributionSideEffects


class BusinessInvestigationContributionBlocked(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class TaskCockpitContributionReader(Protocol):
    def read_skill_contributions(
        self, *, org_id: str, project_id: str, run_id: str
    ) -> TaskCockpitSkillContributionEnvelope: ...

    def read_responsibility_handoffs(
        self, *, org_id: str, project_id: str, run_id: str
    ) -> TaskCockpitResponsibilityHandoffEnvelope: ...


class BusinessInvestigationContributionReader:
    def __init__(self, cockpit: TaskCockpitContributionReader) -> None:
        self._cockpit = cockpit

    def read(
        self,
        scope: TenantScope,
        compilation: BusinessInvestigationCompilation,
        runtime: BusinessInvestigationRuntimeBinding,
    ) -> BusinessInvestigationContributionView:
        tenant = TenantContext(org_id=scope.org_id, project_id=scope.project_id)
        if compilation.tenant != tenant or runtime.tenant != tenant:
            raise BusinessInvestigationContributionBlocked("TENANT_DRIFTED")
        if compilation.task_id != runtime.task_ref.resource_id:
            raise BusinessInvestigationContributionBlocked("TASK_DRIFTED")
        run_id = runtime.task_run_ref.resource_id
        skills = self._cockpit.read_skill_contributions(
            org_id=scope.org_id, project_id=scope.project_id, run_id=run_id
        )
        handoffs = self._cockpit.read_responsibility_handoffs(
            org_id=scope.org_id, project_id=scope.project_id, run_id=run_id
        )
        for envelope in (skills, handoffs):
            if envelope.tenant != tenant or envelope.run_id != run_id:
                raise BusinessInvestigationContributionBlocked("ENVELOPE_DRIFTED")
            if envelope.task_id != compilation.task_id:
                raise BusinessInvestigationContributionBlocked("ENVELOPE_TASK_DRIFTED")
        if handoffs.responsibility_plan_ref != compilation.responsibility_plan_ref:
            raise BusinessInvestigationContributionBlocked(
                "RESPONSIBILITY_PLAN_DRIFTED"
            )

        expected_skills = {
            (ref.resource_id, ref.revision, ref.content_hash)
            for ref in compilation.ordered_skill_refs
        }
        for item in skills.items:
            observed = (
                item.skill_revision_ref.resource_id,
                item.skill_revision_ref.revision,
                item.skill_revision_ref.content_hash,
            )
            if observed not in expected_skills:
                raise BusinessInvestigationContributionBlocked("SKILL_REF_DRIFTED")
            if item.logic_revision_ref != compilation.logic_ref:
                raise BusinessInvestigationContributionBlocked("LOGIC_REF_DRIFTED")
            if item.allowed_commands:
                raise BusinessInvestigationContributionBlocked(
                    "CONTRIBUTION_COMMANDS_FORBIDDEN"
                )

        blockers = list(skills.blocker_codes)
        if any(item.readiness.status != "available" for item in skills.items):
            blockers.append("CONTRIBUTION_NOT_CURRENTLY_AVAILABLE")
        if handoffs.handoffs:
            blockers.append("HANDOFF_EXACT_ENVELOPE_HASH_UNAVAILABLE")
        blockers = list(dict.fromkeys(blockers))
        return BusinessInvestigationContributionView(
            tenant=tenant,
            task_id=compilation.task_id,
            run_id=run_id,
            responsibility_plan_ref=compilation.responsibility_plan_ref,
            skill_contributions=skills,
            responsibility_handoffs=handoffs,
            projection_status="blocked" if blockers else "ready",
            blocker_codes=blockers,
            side_effects=BusinessInvestigationContributionSideEffects(),
        )
