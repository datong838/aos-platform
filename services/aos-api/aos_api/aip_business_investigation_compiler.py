"""BI-W5-01 strict adapter from InvestigationProfile to canonical AIP compilation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import hashlib
import json
from typing import Literal, Protocol

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_production_contracts import (
    CompileStageTemplateRequest,
    ExactRevisionRef,
    StageCompilationResult,
)
from aos_api.tenant_scope import TenantScope


AnalysisType = Literal[
    "initial_store_analysis",
    "weekly_business_review",
    "experience_growth",
    "creator_sales",
    "product_structure",
]
StageId = Literal["portrait", "diagnosis", "solution-design"]
STAGE_ORDER: tuple[StageId, ...] = ("portrait", "diagnosis", "solution-design")


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_type(ref: ExactRevisionRef, expected: str, label: str) -> None:
    if ref.resource_type != expected:
        raise ValueError(f"{label} must reference {expected}")


class InvestigationProfileStage(AipContractModel):
    stage_id: StageId
    skill_refs: list[ExactRevisionRef] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def _skills_are_exact_and_unique(self) -> InvestigationProfileStage:
        identities = []
        for ref in self.skill_refs:
            _require_type(ref, "SkillTemplateRevision", "skillRefs")
            identities.append((ref.resource_id, ref.revision, ref.content_hash))
        if len(identities) != len(set(identities)):
            raise ValueError("stage skillRefs must be unique")
        return self


class BusinessInvestigationProfileRevision(AipContractModel):
    schema_version: Literal["aos.aip.business-investigation-profile/v1"] = (
        "aos.aip.business-investigation-profile/v1"
    )
    profile_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    analysis_type: AnalysisType
    compiler_profile: str = Field(min_length=1, max_length=80)
    logic_ref: ExactRevisionRef
    stage_template_ref: ExactRevisionRef
    ordered_skill_refs: list[ExactRevisionRef] = Field(min_length=1, max_length=256)
    skill_binding_set_ref: ExactRevisionRef
    responsibility_plan_ref: ExactRevisionRef
    production_context_ref: ExactRevisionRef
    stages: list[InvestigationProfileStage] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def _profile_is_one_exact_composition(self) -> BusinessInvestigationProfileRevision:
        _require_type(self.logic_ref, "LogicRevision", "logicRef")
        _require_type(
            self.stage_template_ref,
            "StageTemplateRevision",
            "stageTemplateRef",
        )
        _require_type(
            self.skill_binding_set_ref,
            "SkillBindingSetRevision",
            "skillBindingSetRef",
        )
        _require_type(
            self.responsibility_plan_ref,
            "ResponsibilityPlanRevision",
            "responsibilityPlanRef",
        )
        _require_type(
            self.production_context_ref,
            "ProductionContextRevision",
            "productionContextRef",
        )
        if tuple(stage.stage_id for stage in self.stages) != STAGE_ORDER:
            raise ValueError("stages must use portrait, diagnosis, solution-design order")

        ordered = []
        for ref in self.ordered_skill_refs:
            _require_type(ref, "SkillTemplateRevision", "orderedSkillRefs")
            identity = (ref.resource_id, ref.revision, ref.content_hash)
            if identity in ordered:
                raise ValueError("orderedSkillRefs must be unique")
            ordered.append(identity)
        first_use = []
        for stage in self.stages:
            for ref in stage.skill_refs:
                identity = (ref.resource_id, ref.revision, ref.content_hash)
                if identity not in ordered:
                    raise ValueError("stage skillRefs must be declared in orderedSkillRefs")
                if identity not in first_use:
                    first_use.append(identity)
        if first_use != ordered:
            raise ValueError("orderedSkillRefs must equal stable first-use stage order")
        if self.calculated_content_hash() != self.content_hash:
            raise ValueError("InvestigationProfile contentHash mismatch")
        return self

    def calculated_content_hash(self) -> str:
        payload = self.model_dump(mode="json", by_alias=True, exclude={"content_hash"})
        return _canonical_hash(payload)

    @property
    def exact_ref(self) -> ExactRevisionRef:
        return ExactRevisionRef(
            resource_type="InvestigationProfileRevision",
            resource_id=self.profile_id,
            revision=self.revision,
            content_hash=self.content_hash,
        )


class BusinessInvestigationTaskBriefSpec(AipContractModel):
    case_ref: ExactRevisionRef
    run_ref: ExactRevisionRef
    investigation_profile_ref: ExactRevisionRef
    analysis_type: AnalysisType

    @model_validator(mode="after")
    def _ref_types_are_canonical(self) -> BusinessInvestigationTaskBriefSpec:
        _require_type(
            self.case_ref,
            "BusinessInvestigationCaseRevision",
            "caseRef",
        )
        _require_type(self.run_ref, "BusinessInvestigationRun", "runRef")
        _require_type(
            self.investigation_profile_ref,
            "InvestigationProfileRevision",
            "investigationProfileRef",
        )
        return self


class CompileBusinessInvestigationRequest(AipContractModel):
    task_id: str = Field(min_length=1, max_length=200)
    expected_task_version: int = Field(ge=1)
    case_ref: ExactRevisionRef
    run_ref: ExactRevisionRef
    task_brief_ref: ExactRevisionRef
    task_brief_spec: BusinessInvestigationTaskBriefSpec
    profile: BusinessInvestigationProfileRevision

    @model_validator(mode="after")
    def _brief_and_profile_are_exactly_bound(self) -> CompileBusinessInvestigationRequest:
        _require_type(
            self.case_ref,
            "BusinessInvestigationCaseRevision",
            "caseRef",
        )
        _require_type(self.run_ref, "BusinessInvestigationRun", "runRef")
        _require_type(self.task_brief_ref, "TaskBriefRevision", "taskBriefRef")
        if self.task_brief_spec.case_ref != self.case_ref:
            raise ValueError("TaskBrief caseRef mismatch")
        if self.task_brief_spec.run_ref != self.run_ref:
            raise ValueError("TaskBrief runRef mismatch")
        if self.task_brief_spec.investigation_profile_ref != self.profile.exact_ref:
            raise ValueError("TaskBrief investigationProfileRef mismatch")
        if self.task_brief_spec.analysis_type != self.profile.analysis_type:
            raise ValueError("TaskBrief analysisType mismatch")
        return self


class BusinessInvestigationCompilation(AipContractModel):
    tenant: TenantContext
    task_id: str
    case_ref: ExactRevisionRef
    run_ref: ExactRevisionRef
    task_brief_ref: ExactRevisionRef
    profile_ref: ExactRevisionRef
    logic_ref: ExactRevisionRef
    stage_template_ref: ExactRevisionRef
    ordered_skill_refs: list[ExactRevisionRef]
    skill_binding_set_ref: ExactRevisionRef
    responsibility_plan_ref: ExactRevisionRef
    production_context_ref: ExactRevisionRef
    plan_ref: ExactRevisionRef
    normalized_stage_ids: list[StageId]
    stage_compilation_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    compilation_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_authorized: Literal[False] = False
    created_at: datetime


class BusinessInvestigationCompilationBlocked(RuntimeError):
    def __init__(self, code: str, resource_ref: ExactRevisionRef | None = None) -> None:
        self.code = code
        self.resource_ref = resource_ref
        super().__init__(code)


ExactRefResolver = Callable[[TenantScope, ExactRevisionRef], bool]


class StageCompiler(Protocol):
    def compile_stage_template(
        self,
        scope: TenantScope,
        actor: str,
        template_id: str,
        key: str,
        body: CompileStageTemplateRequest,
    ) -> StageCompilationResult: ...


class BusinessInvestigationProfileCompiler:
    """Validate the domain composition, then delegate Plan authority creation."""

    def __init__(
        self,
        stage_compiler: StageCompiler,
        exact_ref_resolver: ExactRefResolver,
    ) -> None:
        self._stage_compiler = stage_compiler
        self._exact_ref_resolver = exact_ref_resolver

    def compile(
        self,
        scope: TenantScope,
        actor: str,
        idempotency_key: str,
        request: CompileBusinessInvestigationRequest,
    ) -> BusinessInvestigationCompilation:
        if not actor.strip() or not idempotency_key.strip():
            raise ValueError("actor and idempotency_key are required")
        refs = self._input_refs(request)
        for label, ref in refs:
            try:
                resolved = self._exact_ref_resolver(scope, ref)
            except Exception as exc:
                raise BusinessInvestigationCompilationBlocked(
                    f"{label}_RESOLUTION_FAILED", ref
                ) from exc
            if not resolved:
                raise BusinessInvestigationCompilationBlocked(
                    f"{label}_NOT_RESOLVED", ref
                )

        profile = request.profile
        stage_result = self._stage_compiler.compile_stage_template(
            scope,
            actor.strip(),
            profile.stage_template_ref.resource_id,
            idempotency_key.strip(),
            CompileStageTemplateRequest(
                task_id=request.task_id,
                expected_task_version=request.expected_task_version,
                template_revision=profile.stage_template_ref.revision,
                template_content_hash=profile.stage_template_ref.content_hash,
                responsibility_plan_ref=profile.responsibility_plan_ref,
                production_context_ref=profile.production_context_ref,
                profile=profile.compiler_profile,
                brief_ref=request.task_brief_ref,
            ),
        )
        self._validate_stage_result(scope, profile, request, stage_result)
        input_snapshot = {
            "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
            "taskId": request.task_id,
            "expectedTaskVersion": request.expected_task_version,
            "refs": [
                {"label": label, **ref.model_dump(mode="json", by_alias=True)}
                for label, ref in refs
            ],
            "analysisType": profile.analysis_type,
            "stages": [
                stage.model_dump(mode="json", by_alias=True)
                for stage in profile.stages
            ],
        }
        input_hash = _canonical_hash(input_snapshot)
        output_snapshot = {
            "inputHash": input_hash,
            "planRef": stage_result.plan_ref.model_dump(mode="json", by_alias=True),
            "stageCompilationHash": stage_result.compilation_hash,
            "normalizedStageIds": stage_result.normalized_stage_ids,
        }
        return BusinessInvestigationCompilation(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            task_id=request.task_id,
            case_ref=request.case_ref,
            run_ref=request.run_ref,
            task_brief_ref=request.task_brief_ref,
            profile_ref=profile.exact_ref,
            logic_ref=profile.logic_ref,
            stage_template_ref=profile.stage_template_ref,
            ordered_skill_refs=profile.ordered_skill_refs,
            skill_binding_set_ref=profile.skill_binding_set_ref,
            responsibility_plan_ref=profile.responsibility_plan_ref,
            production_context_ref=profile.production_context_ref,
            plan_ref=stage_result.plan_ref,
            normalized_stage_ids=stage_result.normalized_stage_ids,
            stage_compilation_hash=stage_result.compilation_hash,
            input_hash=input_hash,
            compilation_hash=_canonical_hash(output_snapshot),
            created_at=stage_result.created_at,
        )

    @staticmethod
    def _input_refs(
        request: CompileBusinessInvestigationRequest,
    ) -> list[tuple[str, ExactRevisionRef]]:
        profile = request.profile
        return [
            ("CASE", request.case_ref),
            ("RUN", request.run_ref),
            ("TASK_BRIEF", request.task_brief_ref),
            ("PROFILE", profile.exact_ref),
            ("LOGIC", profile.logic_ref),
            ("STAGE_TEMPLATE", profile.stage_template_ref),
            *[("SKILL", ref) for ref in profile.ordered_skill_refs],
            ("SKILL_BINDING_SET", profile.skill_binding_set_ref),
            ("RESPONSIBILITY_PLAN", profile.responsibility_plan_ref),
            ("PRODUCTION_CONTEXT", profile.production_context_ref),
        ]

    @staticmethod
    def _validate_stage_result(
        scope: TenantScope,
        profile: BusinessInvestigationProfileRevision,
        request: CompileBusinessInvestigationRequest,
        result: StageCompilationResult,
    ) -> None:
        expected_stages = [stage.stage_id for stage in profile.stages]
        if result.tenant != TenantContext(
            org_id=scope.org_id,
            project_id=scope.project_id,
        ):
            raise BusinessInvestigationCompilationBlocked("STAGE_RESULT_TENANT_MISMATCH")
        if result.task_id != request.task_id:
            raise BusinessInvestigationCompilationBlocked("STAGE_RESULT_TASK_MISMATCH")
        if result.template_ref != profile.stage_template_ref:
            raise BusinessInvestigationCompilationBlocked("STAGE_TEMPLATE_RESULT_DRIFTED")
        if result.responsibility_plan_ref != profile.responsibility_plan_ref:
            raise BusinessInvestigationCompilationBlocked(
                "RESPONSIBILITY_PLAN_RESULT_DRIFTED"
            )
        if result.production_context_ref != profile.production_context_ref:
            raise BusinessInvestigationCompilationBlocked(
                "PRODUCTION_CONTEXT_RESULT_DRIFTED"
            )
        _require_type(result.plan_ref, "PlanRevision", "planRef")
        if result.normalized_stage_ids != expected_stages:
            raise BusinessInvestigationCompilationBlocked("STAGE_ORDER_RESULT_DRIFTED")
