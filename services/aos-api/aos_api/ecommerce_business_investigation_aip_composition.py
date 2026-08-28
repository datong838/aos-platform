"""Read-only resolution of an exact AIP production composition for BI-W10."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


INVESTIGATION_LOGIC_IDS = (
    "ecommerce.logic.D01",
    "ecommerce.logic.D02",
    "ecommerce.logic.D03",
)
INVESTIGATION_SKILL_IDS = (
    "ecommerce.skill.D01",
    "ecommerce.skill.D02",
    "ecommerce.skill.D03",
)
INVESTIGATION_STAGE_IDS = ("portrait", "diagnosis", "solution-design")
INVESTIGATION_RESPONSIBILITY_PROFILE = "ecommerce.business-investigation.readonly"


def _sha(value: str) -> str:
    return value if value.startswith("sha256:") else f"sha256:{value}"


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class AipProductionCompositionObservation(AipContractModel):
    schema_version: str = "aos.ecommerce.business-investigation-aip-composition/v1"
    tenant: TenantContext
    analysis_type: str
    observed_at: datetime
    logic_refs: list[InvestigationExactRef] = Field(default_factory=list)
    skill_refs: list[InvestigationExactRef] = Field(default_factory=list)
    skill_binding_refs: list[InvestigationExactRef] = Field(default_factory=list)
    stage_template_ref: InvestigationExactRef | None = None
    responsibility_plan_ref: InvestigationExactRef | None = None
    production_context_ref: InvestigationExactRef | None = None
    ready: bool = False
    blockers: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ready_requires_complete_unique_refs(self) -> "AipProductionCompositionObservation":
        if self.ready and (
            self.blockers
            or len(self.logic_refs) != len(INVESTIGATION_LOGIC_IDS)
            or len(self.skill_refs) != len(INVESTIGATION_SKILL_IDS)
            or len(self.skill_binding_refs) != len(INVESTIGATION_SKILL_IDS)
            or self.stage_template_ref is None
            or self.responsibility_plan_ref is None
            or self.production_context_ref is None
        ):
            raise ValueError("ready composition requires every exact dependency")
        return self


class AipProductionCompositionSource(Protocol):
    def read(
        self,
        scope: TenantScope,
        analysis_type: str,
        *,
        observed_at: datetime | None = None,
        production_context_ref: InvestigationExactRef | None = None,
    ) -> AipProductionCompositionObservation: ...


class PostgresAipProductionCompositionSource:
    """Observe, but never create or mutate, current production authorities."""

    def __init__(self, connect_factory: Callable[[TenantScope], Any] = db_connect) -> None:
        self._connect = connect_factory

    def read(
        self,
        scope: TenantScope,
        analysis_type: str,
        *,
        observed_at: datetime | None = None,
        production_context_ref: InvestigationExactRef | None = None,
    ) -> AipProductionCompositionObservation:
        now = observed_at or datetime.now(UTC)
        blockers: list[str] = []
        logic_refs: list[InvestigationExactRef] = []
        skill_refs: list[InvestigationExactRef] = []
        binding_refs: list[InvestigationExactRef] = []
        stage_ref: InvestigationExactRef | None = None
        responsibility_ref: InvestigationExactRef | None = None
        context_ref: InvestigationExactRef | None = None

        if analysis_type != "initial_store_analysis":
            blockers.append("AIP_INVESTIGATION_ANALYSIS_TYPE_UNSUPPORTED")

        with self._connect(scope) as conn:
            publications = conn.execute(
                """SELECT publication_id,graph_id,graph_revision,graph_hash
                   FROM aip_logic_publication
                   WHERE org_id=%s AND project_id=%s AND graph_id=ANY(%s)
                   ORDER BY graph_id,graph_revision,publication_id""",
                (*scope.key, list(INVESTIGATION_LOGIC_IDS)),
            ).fetchall()
            skills = conn.execute(
                """SELECT skill_id,revision,canonical_logic_id,lifecycle,content_hash,
                          publication_tenant,logic_revision_ref
                   FROM aip_skill_template_revision
                   WHERE skill_id=ANY(%s) AND lifecycle='published'
                   ORDER BY skill_id,revision""",
                (list(INVESTIGATION_SKILL_IDS),),
            ).fetchall()
            bindings = conn.execute(
                """SELECT binding_id,instance_id,skill_id,skill_revision,status,version,
                          dependency_snapshot_hash,readiness,readiness_reasons,
                          last_evaluated_at,readiness_expires_at
                   FROM aip_skill_binding
                   WHERE org_id=%s AND project_id=%s AND skill_id=ANY(%s)
                     AND status='active'
                   ORDER BY skill_id,skill_revision,binding_id""",
                (*scope.key, list(INVESTIGATION_SKILL_IDS)),
            ).fetchall()
            stages = conn.execute(
                """SELECT template_id,revision,profile,stages,content_hash,lifecycle
                   FROM aip_stage_template_revision
                   WHERE org_id=%s AND project_id=%s
                   ORDER BY template_id,revision""",
                scope.key,
            ).fetchall()
            plans = conn.execute(
                """SELECT plan_id,revision,profile,slots,content_hash,lifecycle
                   FROM aip_responsibility_plan_revision
                   WHERE org_id=%s AND project_id=%s
                   ORDER BY plan_id,revision""",
                scope.key,
            ).fetchall()
            contexts = []
            if production_context_ref is not None:
                contexts = conn.execute(
                    """SELECT context_id,revision,task_id,profile,content_hash,lifecycle,
                              readiness,blockers
                       FROM aip_production_context_revision
                       WHERE org_id=%s AND project_id=%s AND context_id=%s AND revision=%s
                       ORDER BY context_id,revision""",
                    (
                        *scope.key,
                        production_context_ref.resource_id,
                        production_context_ref.revision,
                    ),
                ).fetchall()

        publications_by_logic: dict[str, list[Any]] = defaultdict(list)
        for row in publications:
            publications_by_logic[str(row["graph_id"])].append(row)
        logic_by_id: dict[str, InvestigationExactRef] = {}
        for logic_id in INVESTIGATION_LOGIC_IDS:
            candidates = publications_by_logic[logic_id]
            if not candidates:
                blockers.append("AIP_LOGIC_PUBLICATION_MISSING")
                continue
            if len(candidates) != 1:
                blockers.append("AIP_LOGIC_PUBLICATION_AMBIGUOUS")
                continue
            row = candidates[0]
            exact = InvestigationExactRef(
                resourceType="LogicRevision",
                resourceId=logic_id,
                revision=int(row["graph_revision"]),
                contentHash=_sha(str(row["graph_hash"])),
                receiptId=str(row["publication_id"]),
            )
            logic_refs.append(exact)
            logic_by_id[logic_id] = exact

        skills_by_id: dict[str, list[Any]] = defaultdict(list)
        for row in skills:
            tenant = row["publication_tenant"] or {}
            if tenant.get("orgId") != scope.org_id or tenant.get("projectId") != scope.project_id:
                continue
            skills_by_id[str(row["skill_id"])].append(row)
        selected_skill_by_id: dict[str, Any] = {}
        for skill_id, logic_id in zip(INVESTIGATION_SKILL_IDS, INVESTIGATION_LOGIC_IDS):
            candidates = skills_by_id[skill_id]
            if not candidates:
                blockers.append("AIP_SKILL_PUBLICATION_MISSING")
                continue
            if len(candidates) != 1:
                blockers.append("AIP_SKILL_REVISION_SELECTION_AMBIGUOUS")
                continue
            row = candidates[0]
            selected_skill_by_id[skill_id] = row
            skill_ref = InvestigationExactRef(
                resourceType="SkillTemplateRevision",
                resourceId=skill_id,
                revision=int(row["revision"]),
                contentHash=_sha(str(row["content_hash"])),
            )
            skill_refs.append(skill_ref)
            logic = logic_by_id.get(logic_id)
            declared = row["logic_revision_ref"] or {}
            if logic is None or (
                declared.get("assetType") != "LogicRevision"
                or declared.get("assetId") != logic.resource_id
                or int(declared.get("revision", 0)) != logic.revision
                or _sha(str(declared.get("contentHash", ""))) != logic.content_hash
            ):
                blockers.append("AIP_SKILL_LOGIC_REF_DRIFTED")

        bindings_by_skill: dict[str, list[Any]] = defaultdict(list)
        for row in bindings:
            bindings_by_skill[str(row["skill_id"])].append(row)
        for skill_id in INVESTIGATION_SKILL_IDS:
            selected = selected_skill_by_id.get(skill_id)
            if selected is None:
                continue
            candidates = [
                row
                for row in bindings_by_skill[skill_id]
                if int(row["skill_revision"]) == int(selected["revision"])
            ]
            if not candidates:
                blockers.append("AIP_SKILL_BINDING_MISSING")
                continue
            if len(candidates) != 1:
                blockers.append("AIP_SKILL_BINDING_AMBIGUOUS")
                continue
            row = candidates[0]
            binding_refs.append(
                InvestigationExactRef(
                    resourceType="SkillBindingRevision",
                    resourceId=str(row["binding_id"]),
                    revision=int(row["version"]),
                    contentHash=_canonical_hash(
                        {
                            "tenant": scope.key,
                            "bindingId": row["binding_id"],
                            "instanceId": row["instance_id"],
                            "skillId": row["skill_id"],
                            "skillRevision": row["skill_revision"],
                            "status": row["status"],
                            "version": row["version"],
                            "dependencySnapshotHash": row["dependency_snapshot_hash"],
                        }
                    ),
                )
            )
            expires_at = row["readiness_expires_at"]
            if (
                row["readiness"] != "available"
                or expires_at is None
                or expires_at <= now
            ):
                blockers.append("AIP_SKILL_BINDING_READINESS_STALE")

        matching_stages = [
            row
            for row in stages
            if row["lifecycle"] == "frozen"
            and tuple(stage.get("stageId") for stage in (row["stages"] or []))
            == INVESTIGATION_STAGE_IDS
        ]
        if not matching_stages:
            blockers.append("AIP_INVESTIGATION_STAGE_TEMPLATE_MISSING")
        elif len(matching_stages) != 1:
            blockers.append("AIP_INVESTIGATION_STAGE_TEMPLATE_AMBIGUOUS")
        else:
            row = matching_stages[0]
            stage_ref = InvestigationExactRef(
                resourceType="StageTemplateRevision",
                resourceId=str(row["template_id"]),
                revision=int(row["revision"]),
                contentHash=_sha(str(row["content_hash"])),
            )

        matching_plans = [
            row for row in plans if row["profile"] == INVESTIGATION_RESPONSIBILITY_PROFILE
        ]
        frozen_plans = [row for row in matching_plans if row["lifecycle"] == "frozen"]
        if matching_plans and not frozen_plans:
            blockers.append("AIP_INVESTIGATION_RESPONSIBILITY_PLAN_NOT_FROZEN")
        elif not frozen_plans:
            blockers.append("AIP_INVESTIGATION_RESPONSIBILITY_PLAN_MISSING")
        elif len(frozen_plans) != 1:
            blockers.append("AIP_INVESTIGATION_RESPONSIBILITY_PLAN_AMBIGUOUS")
        else:
            row = frozen_plans[0]
            responsibility_ref = InvestigationExactRef(
                resourceType="ResponsibilityPlanRevision",
                resourceId=str(row["plan_id"]),
                revision=int(row["revision"]),
                contentHash=_sha(str(row["content_hash"])),
            )

        if production_context_ref is None:
            blockers.append("AIP_PRODUCTION_CONTEXT_REQUIRES_RUN")
        elif len(contexts) != 1:
            blockers.append("AIP_PRODUCTION_CONTEXT_MISSING")
        else:
            row = contexts[0]
            observed_ref = InvestigationExactRef(
                resourceType="ProductionContextRevision",
                resourceId=str(row["context_id"]),
                revision=int(row["revision"]),
                contentHash=_sha(str(row["content_hash"])),
            )
            if observed_ref != production_context_ref:
                blockers.append("AIP_PRODUCTION_CONTEXT_REF_DRIFTED")
            elif row["lifecycle"] != "frozen" or row["readiness"] != "ready":
                blockers.append("AIP_PRODUCTION_CONTEXT_NOT_READY")
            else:
                context_ref = observed_ref

        unique_blockers = sorted(set(blockers))
        return AipProductionCompositionObservation(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            analysisType=analysis_type,
            observedAt=now,
            logicRefs=logic_refs,
            skillRefs=skill_refs,
            skillBindingRefs=binding_refs,
            stageTemplateRef=stage_ref,
            responsibilityPlanRef=responsibility_ref,
            productionContextRef=context_ref,
            ready=not unique_blockers,
            blockers=unique_blockers,
        )
