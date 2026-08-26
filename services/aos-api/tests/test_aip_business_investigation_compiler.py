"""BI-W5-01 InvestigationProfile compiler adapter tests."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json

import pytest
from pydantic import ValidationError

from aos_api.aip_business_investigation_compiler import (
    BusinessInvestigationCompilationBlocked,
    BusinessInvestigationProfileCompiler,
    BusinessInvestigationProfileRevision,
    CompileBusinessInvestigationRequest,
)
from aos_api.aip_production_contracts import ExactRevisionRef, StageCompilationResult
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
OTHER_SCOPE = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


def ref(kind: str, identity: str, revision: int = 1, fill: str = "a") -> dict:
    return {
        "resourceType": kind,
        "resourceId": identity,
        "revision": revision,
        "contentHash": fill * 64,
    }


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def profile_payload(**changes) -> dict:
    skills = {
        "scope": ref("SkillTemplateRevision", "freeze-scope", fill="1"),
        "evidence": ref("SkillTemplateRevision", "build-evidence-pack", fill="2"),
        "hypothesis": ref("SkillTemplateRevision", "form-hypotheses", fill="3"),
        "diagnosis": ref("SkillTemplateRevision", "diagnose-metric-change", fill="4"),
        "alternatives": ref("SkillTemplateRevision", "compare-alternatives", fill="5"),
    }
    value = {
        "schemaVersion": "aos.aip.business-investigation-profile/v1",
        "profileId": "initial-store-analysis-v1",
        "revision": 1,
        "contentHash": "0" * 64,
        "analysisType": "initial_store_analysis",
        "compilerProfile": "BUSINESS_INVESTIGATION",
        "logicRef": ref("LogicRevision", "business-investigation", fill="6"),
        "stageTemplateRef": ref(
            "StageTemplateRevision", "business-investigation-three-stage", fill="7"
        ),
        "orderedSkillRefs": list(skills.values()),
        "skillBindingSetRef": ref(
            "SkillBindingSetRevision", "business-investigation-bindings", fill="8"
        ),
        "responsibilityPlanRef": ref(
            "ResponsibilityPlanRevision", "business-investigation-roles", fill="9"
        ),
        "productionContextRef": ref(
            "ProductionContextRevision", "business-investigation-context", fill="b"
        ),
        "stages": [
            {
                "stageId": "portrait",
                "skillRefs": [skills["scope"], skills["evidence"]],
            },
            {
                "stageId": "diagnosis",
                "skillRefs": [skills["evidence"], skills["hypothesis"], skills["diagnosis"]],
            },
            {
                "stageId": "solution-design",
                "skillRefs": [skills["alternatives"]],
            },
        ],
    }
    value.update(changes)
    hashed = {key: item for key, item in value.items() if key != "contentHash"}
    value["contentHash"] = canonical_hash(hashed)
    return value


def compile_request(**changes) -> CompileBusinessInvestigationRequest:
    profile = BusinessInvestigationProfileRevision.model_validate(profile_payload())
    case = ref("BusinessInvestigationCaseRevision", "case-1", revision=2, fill="c")
    run = ref("BusinessInvestigationRun", "run-1", fill="d")
    brief = ref("TaskBriefRevision", "brief-1", fill="e")
    value = {
        "taskId": "task-1",
        "expectedTaskVersion": 1,
        "caseRef": case,
        "runRef": run,
        "taskBriefRef": brief,
        "taskBriefSpec": {
            "caseRef": case,
            "runRef": run,
            "investigationProfileRef": profile.exact_ref.model_dump(
                mode="json", by_alias=True
            ),
            "analysisType": profile.analysis_type,
        },
        "profile": profile.model_dump(mode="json", by_alias=True),
    }
    value.update(changes)
    return CompileBusinessInvestigationRequest.model_validate(value)


def stage_result(**changes) -> StageCompilationResult:
    profile = BusinessInvestigationProfileRevision.model_validate(profile_payload())
    value = {
        "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "taskId": "task-1",
        "templateRef": profile.stage_template_ref.model_dump(mode="json", by_alias=True),
        "responsibilityPlanRef": profile.responsibility_plan_ref.model_dump(
            mode="json", by_alias=True
        ),
        "productionContextRef": profile.production_context_ref.model_dump(
            mode="json", by_alias=True
        ),
        "planRef": ref("PlanRevision", "plan-1", fill="f"),
        "compilerVersion": "w2c.v1",
        "inputHash": "1" * 64,
        "compilationHash": "2" * 64,
        "normalizedStageIds": ["portrait", "diagnosis", "solution-design"],
        "applicableStageIds": ["portrait", "diagnosis", "solution-design"],
        "notApplicableStageIds": [],
        "createdAt": NOW,
    }
    value.update(changes)
    return StageCompilationResult.model_validate(value)


class FixedStageCompiler:
    def __init__(self, result: StageCompilationResult | None = None) -> None:
        self.result = result or stage_result()
        self.calls = []

    def compile_stage_template(self, scope, actor, template_id, key, body):
        self.calls.append((scope, actor, template_id, key, body))
        return self.result


def test_profile_contract_is_exact_atomic_and_stably_ordered() -> None:
    profile = BusinessInvestigationProfileRevision.model_validate(profile_payload())
    assert profile.calculated_content_hash() == profile.content_hash
    assert [stage.stage_id for stage in profile.stages] == [
        "portrait",
        "diagnosis",
        "solution-design",
    ]
    assert profile.exact_ref.resource_type == "InvestigationProfileRevision"

    reversed_stages = list(reversed(profile_payload()["stages"]))
    with pytest.raises(ValidationError, match="portrait, diagnosis, solution-design"):
        BusinessInvestigationProfileRevision.model_validate(
            profile_payload(stages=reversed_stages)
        )
    duplicate = profile_payload()
    duplicate["orderedSkillRefs"] = [
        duplicate["orderedSkillRefs"][0],
        duplicate["orderedSkillRefs"][0],
    ]
    duplicate["contentHash"] = canonical_hash(
        {key: value for key, value in duplicate.items() if key != "contentHash"}
    )
    with pytest.raises(ValidationError, match="orderedSkillRefs must be unique"):
        BusinessInvestigationProfileRevision.model_validate(duplicate)


def test_compiler_delegates_plan_authority_and_is_deterministic() -> None:
    stage_compiler = FixedStageCompiler()
    resolved = []

    def resolver(scope, exact_ref):
        resolved.append((scope, exact_ref))
        return scope == SCOPE

    compiler = BusinessInvestigationProfileCompiler(stage_compiler, resolver)
    request = compile_request()
    first = compiler.compile(SCOPE, "owner", "compile-1", request)
    second = compiler.compile(SCOPE, "owner", "compile-1", request)

    assert first.input_hash == second.input_hash
    assert first.compilation_hash == second.compilation_hash
    assert first.plan_ref == stage_compiler.result.plan_ref
    assert first.runtime_authorized is False
    assert first.ordered_skill_refs == request.profile.ordered_skill_refs
    assert len(resolved) == 2 * len(compiler._input_refs(request))
    assert len(stage_compiler.calls) == 2
    _, actor, template_id, key, body = stage_compiler.calls[0]
    assert (actor, template_id, key) == (
        "owner",
        request.profile.stage_template_ref.resource_id,
        "compile-1",
    )
    assert body.brief_ref == request.task_brief_ref
    assert body.responsibility_plan_ref == request.profile.responsibility_plan_ref
    assert body.production_context_ref == request.profile.production_context_ref


def test_unresolved_or_cross_tenant_ref_blocks_before_plan_creation() -> None:
    stage_compiler = FixedStageCompiler()
    request = compile_request()

    def missing_binding(_scope, exact_ref):
        return exact_ref.resource_type != "SkillBindingSetRevision"

    with pytest.raises(
        BusinessInvestigationCompilationBlocked,
        match="SKILL_BINDING_SET_NOT_RESOLVED",
    ):
        BusinessInvestigationProfileCompiler(
            stage_compiler, missing_binding
        ).compile(SCOPE, "owner", "compile-1", request)
    assert stage_compiler.calls == []

    with pytest.raises(BusinessInvestigationCompilationBlocked, match="CASE_NOT_RESOLVED"):
        BusinessInvestigationProfileCompiler(
            stage_compiler, lambda scope, _ref: scope == SCOPE
        ).compile(OTHER_SCOPE, "owner", "compile-1", request)
    assert stage_compiler.calls == []


def test_task_brief_or_stage_compilation_drift_fails_closed() -> None:
    request = compile_request()
    wrong_case = ref(
        "BusinessInvestigationCaseRevision", "case-other", revision=2, fill="c"
    )
    brief_spec = request.task_brief_spec.model_dump(mode="json", by_alias=True)
    brief_spec["caseRef"] = wrong_case
    with pytest.raises(ValidationError, match="TaskBrief caseRef mismatch"):
        compile_request(taskBriefSpec=brief_spec)

    drifted = stage_result(normalizedStageIds=["portrait", "solution-design", "diagnosis"])
    stage_compiler = FixedStageCompiler(drifted)
    with pytest.raises(
        BusinessInvestigationCompilationBlocked,
        match="STAGE_ORDER_RESULT_DRIFTED",
    ):
        BusinessInvestigationProfileCompiler(
            stage_compiler, lambda _scope, _ref: True
        ).compile(SCOPE, "owner", "compile-1", request)


def test_profile_rejects_parallel_or_non_exact_authority_types() -> None:
    bad = profile_payload(
        logicRef=ref("BusinessInvestigationLogic", "private-copy", fill="6")
    )
    with pytest.raises(ValidationError, match="logicRef must reference LogicRevision"):
        BusinessInvestigationProfileRevision.model_validate(bad)
    bad = profile_payload(
        skillBindingSetRef=ref("UiRoleState", "analyst-online", fill="8")
    )
    with pytest.raises(
        ValidationError,
        match="skillBindingSetRef must reference SkillBindingSetRevision",
    ):
        BusinessInvestigationProfileRevision.model_validate(bad)
