"""W8-03 TaskGraph-rooted cross-domain dispatch contribution tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_dispatch_scenario import (
    DispatchScenarioObservation,
    EcommerceWorkshopDispatchScenario,
    dispatch_binding_hash,
)
from aos_api.ecommerce_workshop_dispatch_scenario_contracts import (
    DispatchScenarioBlocker,
    DispatchScenarioComposition,
    DispatchScenarioContribution,
    DispatchScenarioDecisionLedger,
    DispatchScenarioExactRef,
    DispatchScenarioOutcomeAxis,
    DispatchScenarioOutcomeAxisId,
    DispatchScenarioRoleBinding,
    DispatchScenarioStage,
    DispatchScenarioStageId,
)
from aos_api.tenant_scope import TenantScope


CUTOFF = datetime(2026, 8, 26, 4, tzinfo=UTC)
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")
HASH = "sha256:" + "a" * 64


def ref(resource_type: str, resource_id: str) -> DispatchScenarioExactRef:
    return DispatchScenarioExactRef(
        resourceType=resource_type,
        resourceId=resource_id,
        revision=1,
        contentHash=HASH,
    )


def blocker(code: str) -> DispatchScenarioBlocker:
    return DispatchScenarioBlocker(
        code=code,
        dependency="workshop.dispatch-scenario",
        requiredAction="provide exact current evidence",
    )


def composition() -> DispatchScenarioComposition:
    return DispatchScenarioComposition(
        atomicSkillRefs=[ref("SkillRevision", "prepare-handoff"), ref("SkillRevision", "plan-responsibilities")],
        logicRevisionRef=ref("LogicRevision", "daily-control-dispatch"),
        roleBindings=[
            DispatchScenarioRoleBinding(
                roleRef=ref("AgentTemplate", "operations-lead"),
                assigneeRef=ref("AgentInstance", "operations-lead-1"),
                skillBindingRef=ref("SkillBinding", "binding-1"),
            )
        ],
    )


def stages(
    graph: DispatchScenarioExactRef | None = None,
    run: DispatchScenarioExactRef | None = None,
) -> tuple[DispatchScenarioStage, ...]:
    graph = graph or ref("TaskGraphRevision", "graph-1")
    run = run or ref("TaskRun", "run-1")
    refs = [
        [graph, run],
        [ref("DispatchIntentRevision", "intent-1")],
        [ref("HandoffEnvelopeRevision", "handoff-1")],
        [ref("HandoffDecisionRevision", "decision-1")],
        [ref("ContextRequirementRevision", "gap-1")],
        [ref("TakeoverRequestRevision", "takeover-1")],
        [ref("OwnerTimelineRevision", "owner-timeline-1")],
    ]
    return tuple(
        DispatchScenarioStage(
            stageId=stage,
            status="ready",
            exactRefs=refs[index],
            contribution=f"stage {stage.value}",
        )
        for index, stage in enumerate(DispatchScenarioStageId)
    )


def axes(*, all_ready: bool = False) -> tuple[DispatchScenarioOutcomeAxis, ...]:
    result = [
        DispatchScenarioOutcomeAxis(axisId=axis, status="ready", exactRef=ref("DecisionReceiptRevision", axis.value))
        for axis in DispatchScenarioOutcomeAxisId
    ]
    if not all_ready:
        result[-1] = DispatchScenarioOutcomeAxis(
            axisId=DispatchScenarioOutcomeAxisId.EXECUTION_RECONCILIATION,
            status="unknown",
            blocker=blocker("PROVIDER_OUTCOME_UNKNOWN_RECONCILIATION_REQUIRED"),
        )
    return tuple(result)


def ledger() -> DispatchScenarioDecisionLedger:
    return DispatchScenarioDecisionLedger(
        tasksExpected=1,
        tasksObserved=1,
        handoffsExpected=1,
        handoffsObserved=1,
        decisionsExpected=2,
        decisionsRecorded=2,
        accepted=1,
        rejected=0,
        requestMore=1,
        returned=0,
        takeoverRequested=1,
        takeoverDecided=1,
        activeOwnerCount=1,
    )


class Reader:
    def __init__(
        self,
        *,
        scope: TenantScope = SCOPE,
        binding: str | None = None,
        root_drift: bool = False,
        all_ready: bool = False,
    ) -> None:
        self.scope = scope
        self.binding = binding
        self.root_drift = root_drift
        self.all_ready = all_ready

    def read_scenario(self, scope: TenantScope, *, cutoff: datetime) -> DispatchScenarioObservation:
        graph = ref("TaskGraphRevision", "graph-1")
        run = ref("TaskRun", "run-1")
        layer = composition()
        stage_items = stages(
            ref("TaskGraphRevision", "graph-drift") if self.root_drift else graph,
            run,
        )
        return DispatchScenarioObservation(
            scope=self.scope,
            cutoff=cutoff,
            root_task_graph_ref=graph,
            root_task_run_ref=run,
            dispatch_binding_hash=self.binding or dispatch_binding_hash(graph, run, layer, stage_items),
            composition=layer,
            stages=stage_items,
            ledger=ledger(),
            outcome_axes=axes(all_ready=self.all_ready),
        )


def test_missing_root_returns_structured_blocked_contribution() -> None:
    result = EcommerceWorkshopDispatchScenario().read(scope=SCOPE, cutoff=CUTOFF)
    assert result.root_task_graph_ref is None
    assert [item.stage_id for item in result.stages] == list(DispatchScenarioStageId)
    assert [item.axis_id for item in result.outcome_axes] == list(DispatchScenarioOutcomeAxisId)
    assert result.commands.model_dump() == {
        "dispatch": False,
        "decide_handoff": False,
        "request_takeover": False,
        "approve_takeover": False,
        "mutate_owner": False,
    }
    assert result.external_effects_allowed is False


def test_exact_binding_keeps_atomic_skill_logic_role_and_outcomes_separate() -> None:
    result = EcommerceWorkshopDispatchScenario(reader=Reader()).read(scope=SCOPE, cutoff=CUTOFF)
    assert result.root_task_graph_ref and result.root_task_graph_ref.resource_type == "TaskGraphRevision"
    assert result.composition and len(result.composition.atomic_skill_refs) == 2
    assert result.composition.logic_revision_ref.resource_type == "LogicRevision"
    assert result.composition.role_bindings[0].skill_binding_ref.resource_type == "SkillBinding"
    assert [item.status for item in result.outcome_axes] == ["ready", "ready", "ready", "ready", "unknown"]
    assert result.ledger.active_owner_count == 1
    assert result.status == "blocked"


def test_cross_tenant_binding_and_root_drift_fail_closed_without_refs() -> None:
    other = TenantScope(org_id="dev-org", project_id="dev-project")
    tenant_result = EcommerceWorkshopDispatchScenario(reader=Reader(scope=other)).read(scope=SCOPE, cutoff=CUTOFF)
    binding_result = EcommerceWorkshopDispatchScenario(reader=Reader(binding="f" * 64)).read(scope=SCOPE, cutoff=CUTOFF)
    root_result = EcommerceWorkshopDispatchScenario(reader=Reader(root_drift=True)).read(scope=SCOPE, cutoff=CUTOFF)
    assert tenant_result.blockers[0].code == "DISPATCH_SCENARIO_SCOPE_OR_CUTOFF_DRIFT"
    assert binding_result.blockers[0].code == "DISPATCH_SCENARIO_BINDING_DRIFT"
    assert root_result.blockers[0].code == "TASK_GRAPH_ROOT_STAGE_DRIFT"
    assert tenant_result.root_task_graph_ref is binding_result.root_task_graph_ref is root_result.root_task_graph_ref is None


def test_all_ready_operational_claim_is_replaced_by_explicit_gate_blocker() -> None:
    result = EcommerceWorkshopDispatchScenario(reader=Reader(all_ready=True)).read(scope=SCOPE, cutoff=CUTOFF)
    assert result.root_task_graph_ref is None
    assert result.blockers[0].code == "DISPATCH_SCENARIO_OPERATIONAL_AUTHORIZATION_REQUIRED"


def test_decision_conservation_and_layer_aliasing_are_rejected() -> None:
    with pytest.raises(ValidationError):
        DispatchScenarioDecisionLedger(
            tasksExpected=1,
            tasksObserved=1,
            handoffsExpected=1,
            handoffsObserved=1,
            decisionsExpected=1,
            decisionsRecorded=1,
            accepted=1,
            rejected=1,
            requestMore=0,
            returned=0,
            takeoverRequested=0,
            takeoverDecided=0,
            activeOwnerCount=1,
        )
    with pytest.raises(ValidationError):
        DispatchScenarioComposition(
            atomicSkillRefs=[ref("LogicRevision", "not-a-skill")],
            logicRevisionRef=ref("LogicRevision", "logic-1"),
            roleBindings=composition().role_bindings,
        )


def test_fully_ready_contract_cannot_claim_operational_green() -> None:
    graph = ref("TaskGraphRevision", "graph-1")
    run = ref("TaskRun", "run-1")
    layer = composition()
    stage_items = stages(graph, run)
    with pytest.raises(ValidationError):
        DispatchScenarioContribution(
            rootTaskGraphRef=graph,
            rootTaskRunRef=run,
            dispatchBindingHash=dispatch_binding_hash(graph, run, layer, stage_items),
            composition=layer,
            evaluatedAt=CUTOFF,
            stages=list(stage_items),
            ledger=ledger(),
            outcomeAxes=list(axes(all_ready=True)),
            blockers=[blocker("OPERATIONAL_AUTHORIZATION_REQUIRED")],
        )
