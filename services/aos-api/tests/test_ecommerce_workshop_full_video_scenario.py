"""W8-05 FULL video production and fault-recovery scenario tests."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_full_video_scenario import (
    EcommerceWorkshopFullVideoScenario,
    FullVideoScenarioObservation,
    full_production_binding_hash,
)
from aos_api.ecommerce_workshop_full_video_scenario_contracts import (
    FullVideoBlocker,
    FullVideoComposition,
    FullVideoExactRef,
    FullVideoFaultId,
    FullVideoFaultRecovery,
    FullVideoLedger,
    FullVideoResponsibility,
    FullVideoResponsibilityId,
    FullVideoRoleBinding,
    FullVideoStage,
    FullVideoStageId,
)
from aos_api.tenant_scope import TenantScope


CUTOFF = datetime(2026, 8, 26, 6, tzinfo=UTC)
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")
HASH = "sha256:" + "a" * 64


def ref(resource_type: str, resource_id: str) -> FullVideoExactRef:
    return FullVideoExactRef(resourceType=resource_type, resourceId=resource_id, revision=1, contentHash=HASH)


def blocker(code: str) -> FullVideoBlocker:
    return FullVideoBlocker(code=code, dependency="workshop.full-video", requiredAction="append exact current evidence")


def composition() -> FullVideoComposition:
    return FullVideoComposition(
        atomicSkillRefs=[ref("SkillRevision", "media-script"), ref("SkillRevision", "media-gate-review")],
        logicRevisionRef=ref("LogicRevision", "full-short-video-production"),
        roleBindings=[
            FullVideoRoleBinding(
                roleRef=ref("AgentTemplate", "content-officer"),
                assigneeRef=ref("AgentInstance", "content-officer-1"),
                skillBindingRef=ref("SkillBinding", "media-script-binding"),
            )
        ],
    )


def responsibilities() -> tuple[FullVideoResponsibility, ...]:
    return tuple(
        FullVideoResponsibility(
            responsibilityId=item,
            label=item.value,
            status="assigned",
            assigneeRef=ref("AgentInstance", f"assignee-{index % 3}"),
            skillBindingRef=ref("SkillBinding", f"binding-{index}"),
            independentReviewRequired=item is FullVideoResponsibilityId.REVIEW,
        )
        for index, item in enumerate(FullVideoResponsibilityId)
    )


def stages(brief: FullVideoExactRef, run: FullVideoExactRef) -> tuple[FullVideoStage, ...]:
    stage_refs = [
        [brief, ref("ProfileConfirmationReceipt", "profile-1")],
        [run, ref("StageCompilationReceipt", "compile-1")],
        [ref("ArtifactRevision", "script-1"), ref("ArtifactRevision", "art-1")],
        [ref("ArtifactRevision", "storyboard-1"), ref("ArtifactRevision", "raw-1")],
        [ref("ArtifactRevision", "master-1"), ref("MediaGateSetDecision", "gate-set-1")],
        [],
        [],
    ]
    return tuple(
        FullVideoStage(stageId=item, status="ready", exactRefs=stage_refs[index], contribution=f"stage {item.value}")
        if stage_refs[index]
        else FullVideoStage(stageId=item, status="blocked", contribution="外部发布或结算未授权", blocker=blocker("FULL_VIDEO_EXTERNAL_GATE_REQUIRED"))
        for index, item in enumerate(FullVideoStageId)
    )


def faults() -> tuple[FullVideoFaultRecovery, ...]:
    result = []
    for item in FullVideoFaultId:
        if item is FullVideoFaultId.RESTART_PARTITION:
            result.append(FullVideoFaultRecovery(faultId=item, status="unknown", recoveryDecision="等待重启 EvidencePack", blocker=blocker("FULL_VIDEO_RESTART_EVIDENCE_REQUIRED")))
        else:
            result.append(FullVideoFaultRecovery(faultId=item, status="ready", recoveryDecision=f"durable decision {item.value}", authorityRefs=[ref("RecoveryDecisionReceipt", f"recovery-{item.value}")]))
    return tuple(result)


class Reader:
    def __init__(self, *, scope: TenantScope = SCOPE, binding: str | None = None, root_drift: bool = False, all_ready: bool = False) -> None:
        self.scope = scope
        self.binding = binding
        self.root_drift = root_drift
        self.all_ready = all_ready

    def read_scenario(self, scope: TenantScope, *, cutoff: datetime) -> FullVideoScenarioObservation:
        brief = ref("MediaProductionBriefRevision", "brief-1")
        run = ref("TaskRun", "run-1")
        stage_items = stages(ref("MediaProductionBriefRevision", "brief-drift") if self.root_drift else brief, run)
        fault_items = faults()
        if self.all_ready:
            stage_items = tuple(FullVideoStage(stageId=item, status="ready", exactRefs=[brief if item is FullVideoStageId.BRIEF_PROFILE else run if item is FullVideoStageId.COMPILE_START else ref("ScenarioEvidence", item.value)], contribution="ready") for item in FullVideoStageId)
            fault_items = tuple(FullVideoFaultRecovery(faultId=item, status="ready", recoveryDecision="ready", authorityRefs=[ref("RecoveryDecisionReceipt", item.value)]) for item in FullVideoFaultId)
        observed = FullVideoScenarioObservation(
            scope=self.scope,
            cutoff=cutoff,
            root_brief_ref=brief,
            task_run_ref=run,
            full_production_binding_hash="0" * 64,
            composition=composition(),
            responsibilities=responsibilities(),
            stages=stage_items,
            fault_recovery=fault_items,
            ledger=FullVideoLedger(
                responsibilitiesObserved=8,
                stagesObserved=sum(item.status == "ready" for item in stage_items),
                attemptsExpected=5,
                attemptsObserved=5,
                artifactsExpected=6,
                artifactsObserved=6,
                mediaGatesObserved=4,
                faultCasesObserved=sum(item.status == "ready" for item in fault_items),
                usageBucketsExpected=2,
                usageBucketsObserved=2,
            ),
        )
        return replace(observed, full_production_binding_hash=self.binding or full_production_binding_hash(observed))


def test_missing_root_returns_complete_blocked_matrix() -> None:
    result = EcommerceWorkshopFullVideoScenario().read(scope=SCOPE, cutoff=CUTOFF)
    assert result.root_brief_ref is None and result.task_run_ref is None
    assert [item.stage_id for item in result.stages] == list(FullVideoStageId)
    assert [item.responsibility_id for item in result.responsibilities] == list(FullVideoResponsibilityId)
    assert [item.fault_id for item in result.fault_recovery] == list(FullVideoFaultId)
    assert all(value is False for value in result.commands.model_dump().values())
    assert result.external_effects_allowed is result.release_allowed is False


def test_exact_binding_preserves_four_layers_eight_roles_and_fault_axes() -> None:
    result = EcommerceWorkshopFullVideoScenario(reader=Reader()).read(scope=SCOPE, cutoff=CUTOFF)
    assert result.root_brief_ref and result.root_brief_ref.resource_type == "MediaProductionBriefRevision"
    assert result.task_run_ref and result.task_run_ref.resource_type == "TaskRun"
    assert result.composition and len(result.composition.atomic_skill_refs) == 2
    assert result.composition.logic_revision_ref.resource_type == "LogicRevision"
    assert len(result.responsibilities) == result.ledger.responsibilities_observed == 8
    assert result.ledger.media_gates_observed == result.ledger.media_gates_expected == 4
    assert len(result.fault_recovery) == 9 and result.ledger.fault_cases_observed == 8
    assert result.status == "blocked"


def test_tenant_binding_and_root_drift_fail_closed_without_refs() -> None:
    other = TenantScope(org_id="dev-org", project_id="dev-project")
    tenant = EcommerceWorkshopFullVideoScenario(reader=Reader(scope=other)).read(scope=SCOPE, cutoff=CUTOFF)
    binding = EcommerceWorkshopFullVideoScenario(reader=Reader(binding="f" * 64)).read(scope=SCOPE, cutoff=CUTOFF)
    root = EcommerceWorkshopFullVideoScenario(reader=Reader(root_drift=True)).read(scope=SCOPE, cutoff=CUTOFF)
    assert tenant.blockers[0].code == "FULL_VIDEO_SCOPE_OR_CUTOFF_DRIFT"
    assert binding.blockers[0].code == "FULL_VIDEO_BINDING_DRIFT"
    assert root.blockers[0].code == "FULL_VIDEO_ROOT_STAGE_DRIFT"
    assert tenant.root_brief_ref is binding.root_brief_ref is root.root_brief_ref is None


def test_fully_ready_operational_claim_is_replaced_by_gate_blocker() -> None:
    result = EcommerceWorkshopFullVideoScenario(reader=Reader(all_ready=True)).read(scope=SCOPE, cutoff=CUTOFF)
    assert result.root_brief_ref is None
    assert result.blockers[0].code == "FULL_VIDEO_OPERATIONAL_AUTHORIZATION_REQUIRED"


def test_ledger_and_layer_aliasing_are_rejected() -> None:
    with pytest.raises(ValidationError):
        FullVideoLedger(
            responsibilitiesObserved=8, stagesObserved=7, attemptsExpected=1, attemptsObserved=2,
            artifactsExpected=1, artifactsObserved=1, mediaGatesObserved=4, faultCasesObserved=9,
            usageBucketsExpected=1, usageBucketsObserved=1,
        )
    with pytest.raises(ValidationError):
        FullVideoComposition(
            atomicSkillRefs=[ref("LogicRevision", "not-a-skill")],
            logicRevisionRef=ref("LogicRevision", "logic-1"),
            roleBindings=composition().role_bindings,
        )
