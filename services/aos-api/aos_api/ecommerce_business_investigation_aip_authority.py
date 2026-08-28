"""Deterministic BI stage, responsibility and Skill-selection authorities."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from aos_api.aip_contracts import ResourceRef
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import (
    AssigneeKind,
    AssigneeRef,
    BriefLifecycle,
    ContractReadiness,
    CreateResponsibilityPlanRequest,
    CreateStageTemplateRequest,
    ExactRevisionRef,
    ResponsibilityPlanRevision,
    ResponsibilitySlot,
    StageApplicability,
    StageApplicabilityKind,
    StageDefinition,
    StageTemplateRevision,
)
from aos_api.aip_responsibility_template_authority import (
    published_template_ref,
    resolve_responsibility_template,
)
from aos_api.aip_stage_template_authority import (
    published_investigation_profile_source_ref,
    resolve_stage_template_source,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


INVESTIGATION_SKILL_SELECTION: tuple[ExactRevisionRef, ...] = (
    ExactRevisionRef(
        resourceType="SkillTemplateRevision",
        resourceId="ecommerce.skill.D01",
        revision=2,
        contentHash="d204a147231dbdeb04c96e0ee93989aaf73088ba4ac5e72261efa063135a4b6d",
    ),
    ExactRevisionRef(
        resourceType="SkillTemplateRevision",
        resourceId="ecommerce.skill.D02",
        revision=2,
        contentHash="342ff31d2c01365fbdcc4d27520e9ee711f96ccfc0851b5c94992fc7a0440952",
    ),
    ExactRevisionRef(
        resourceType="SkillTemplateRevision",
        resourceId="ecommerce.skill.D03",
        revision=4,
        contentHash="3b60ef1e7147b761d1582d8dd0c62934e24d28a8ad8306caf12b1db02306a704",
    ),
)

_ROLE_BLUEPRINTS = (
    ("investigation-owner", "investigation_owner", "ecommerce.data_advisor.default", ("strategy.plan",), "portrait"),
    ("data-steward", "data_steward", "ecommerce.customer_service.default", ("material.collect",), "portrait"),
    ("content-research", "content_research", "ecommerce.content_officer.default", ("content.review",), "diagnosis"),
    ("customer-research", "customer_research", "ecommerce.private_domain_manager.default", ("material.collect",), "diagnosis"),
    ("channel-research", "channel_research", "ecommerce.campaign_planner.default", ("strategy.plan",), "solution-design"),
    ("business-reviewer", "business_review", "ecommerce.shopping_advisor.default", ("strategy.plan",), "solution-design"),
)


def selected_skill_refs() -> dict[str, ExactRevisionRef]:
    return {ref.resource_id: ref for ref in INVESTIGATION_SKILL_SELECTION}


def _schema(resource_id: str) -> ResourceRef:
    return ResourceRef(
        resourceType="JsonSchema",
        resourceId=resource_id,
        revision="1",
        authority="aos.ecommerce.business-investigation",
    )


def build_stage_template_request() -> CreateStageTemplateRequest:
    common = {
        "applicability": StageApplicability(kind=StageApplicabilityKind.ALWAYS),
        "gate_refs": [],
        "checkpoint_policy": {"mode": "receipt-first", "unknown": "pause"},
        "retry_policy": {"automatic": False},
        "compensation_policy": {"externalEffect": "none"},
    }
    stages = [
        StageDefinition(
            stageId="portrait",
            title="经营画像",
            dependsOn=[],
            requiredSlotIds=[
                "investigation-owner",
                "data-steward",
                "content-research",
                "customer-research",
                "channel-research",
            ],
            inputSchemaRef=_schema("business-investigation.portrait.input"),
            outputSchemaRef=_schema("business-investigation.portrait.output"),
            **common,
        ),
        StageDefinition(
            stageId="diagnosis",
            title="问题与机会诊断",
            dependsOn=["portrait"],
            requiredSlotIds=[
                "investigation-owner",
                "data-steward",
                "customer-research",
                "channel-research",
                "business-reviewer",
            ],
            inputSchemaRef=_schema("business-investigation.diagnosis.input"),
            outputSchemaRef=_schema("business-investigation.diagnosis.output"),
            **common,
        ),
        StageDefinition(
            stageId="solution-design",
            title="方案设计",
            dependsOn=["diagnosis"],
            requiredSlotIds=[
                "investigation-owner",
                "content-research",
                "channel-research",
                "business-reviewer",
            ],
            inputSchemaRef=_schema("business-investigation.solution-design.input"),
            outputSchemaRef=_schema("business-investigation.solution-design.output"),
            **common,
        ),
    ]
    return CreateStageTemplateRequest(
        profile="ecommerce.business-investigation",
        sourceBundleRef=published_investigation_profile_source_ref(),
        stages=stages,
    )


def build_responsibility_plan_request(
    instance_versions: Mapping[str, int],
) -> CreateResponsibilityPlanRequest:
    missing = sorted(
        instance_id
        for _, _, instance_id, _, _ in _ROLE_BLUEPRINTS
        if instance_id not in instance_versions
    )
    if missing:
        raise ValueError("active digital coworker versions missing: " + ",".join(missing))
    slots = [
        ResponsibilitySlot(
            slotId=slot_id,
            responsibilityType=responsibility_type,
            requiredCapabilityIds=list(capabilities),
            inputSchemaRef=_schema(f"business-investigation.{slot_id}.input"),
            outputSchemaRef=_schema(f"business-investigation.{slot_id}.output"),
            gateRefs=[],
            returnStage=return_stage,
            assignee=AssigneeRef(
                kind=AssigneeKind.AGENT_INSTANCE,
                resourceId=instance_id,
                version=instance_versions[instance_id],
            ),
        )
        for slot_id, responsibility_type, instance_id, capabilities, return_stage in _ROLE_BLUEPRINTS
    ]
    return CreateResponsibilityPlanRequest(
        profile="ecommerce.business-investigation.readonly",
        templateRef=published_template_ref("ecommerce.business-investigation.readonly"),
        slots=slots,
    )


@dataclass(frozen=True)
class InvestigationAuthorityMaterialization:
    stage_template: StageTemplateRevision
    responsibility_plan: ResponsibilityPlanRevision


class BusinessInvestigationAuthorityMaterializer:
    """Idempotently materialize governed metadata; never fabricate readiness."""

    def __init__(
        self,
        *,
        store: AipProductionContractStore | None = None,
        connect_factory: Callable[[TenantScope], Any] = db_connect,
    ) -> None:
        self._connect = connect_factory
        self._store = store or AipProductionContractStore(
            connect_factory=connect_factory,
            responsibility_template_resolver=resolve_responsibility_template,
            stage_template_source_resolver=resolve_stage_template_source,
        )

    def ensure(
        self,
        scope: TenantScope,
        *,
        actor: str = "aos-main-development",
    ) -> InvestigationAuthorityMaterialization:
        versions = self._active_instance_versions(scope)
        stage = self._store.create_stage_template(
            scope,
            actor,
            "bi-w10-02-investigation-stage-v1-create",
            build_stage_template_request(),
        )
        # A create Receipt replays the original draft revision while the head may
        # already have advanced to a frozen revision.  Always decide from the
        # current head so recovery is idempotent and never changes freeze input.
        stage = self._store.get_stage_template(scope, stage.template_id)
        if stage.lifecycle is BriefLifecycle.DRAFT:
            stage = self._store.freeze_stage_template(
                scope,
                actor,
                stage.template_id,
                stage.version,
                "bi-w10-02-investigation-stage-v1-freeze",
            )
        plan = self._store.create_responsibility_plan(
            scope,
            actor,
            "bi-w10-02-investigation-responsibility-v1-create",
            build_responsibility_plan_request(versions),
        )
        plan = self._store.get_responsibility_plan(scope, plan.plan_id)
        if (
            plan.lifecycle is BriefLifecycle.DRAFT
            and plan.readiness is ContractReadiness.READY
        ):
            plan = self._store.freeze_responsibility_plan(
                scope,
                actor,
                plan.plan_id,
                plan.version,
                "bi-w10-02-investigation-responsibility-v1-freeze",
            )
        return InvestigationAuthorityMaterialization(stage, plan)

    def _active_instance_versions(self, scope: TenantScope) -> dict[str, int]:
        instance_ids = [item[2] for item in _ROLE_BLUEPRINTS]
        with self._connect(scope) as conn:
            rows = conn.execute(
                """SELECT instance_id,version FROM aip_agent_instance
                   WHERE org_id=%s AND project_id=%s AND status='active'
                     AND instance_id=ANY(%s) ORDER BY instance_id""",
                (*scope.key, instance_ids),
            ).fetchall()
        return {str(row["instance_id"]): int(row["version"]) for row in rows}
