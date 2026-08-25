"""W8-01 GrowthPlan-rooted scenario contribution tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_growth_scenario import EcommerceWorkshopGrowthScenario, GrowthScenarioObservation, scenario_binding_hash
from aos_api.ecommerce_workshop_growth_scenario_contracts import GrowthScenarioBlocker, GrowthScenarioConservationLedger, GrowthScenarioContribution, GrowthScenarioExactRef, GrowthScenarioOutcomeAxis, GrowthScenarioOutcomeAxisId, GrowthScenarioStage, GrowthScenarioStageId
from aos_api.tenant_scope import TenantScope


CUTOFF = datetime(2026, 8, 26, 3, tzinfo=UTC)
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")
HASH = "sha256:" + "a" * 64


def ref(resource_type: str, resource_id: str) -> GrowthScenarioExactRef:
    return GrowthScenarioExactRef(resourceType=resource_type, resourceId=resource_id, revision=1, contentHash=HASH)


def blocker(code: str) -> GrowthScenarioBlocker:
    return GrowthScenarioBlocker(code=code, dependency="workshop.growth-scenario", requiredAction="provide exact current evidence")


def stages(root: GrowthScenarioExactRef | None = None) -> tuple[GrowthScenarioStage, ...]:
    types = ["InsightRevision", "GrowthPlanRevision", "ContentBriefRevision", "CreatorCollaborationRevision", "MediaProductionRunRevision", "PublishCandidateRevision", "EffectReviewRevision", "MemoryCandidateRevision"]
    refs = [ref(resource_type, f"item-{index}") for index, resource_type in enumerate(types)]
    refs[1] = root or ref("GrowthPlanRevision", "plan-1")
    return tuple(GrowthScenarioStage(stageId=stage, status="ready", exactRefs=[refs[index]], contribution=f"stage {stage.value}") for index, stage in enumerate(GrowthScenarioStageId))


def axes() -> tuple[GrowthScenarioOutcomeAxis, ...]:
    return (
        GrowthScenarioOutcomeAxis(axisId="provider_applied", status="ready", exactRef=ref("ActionReceipt", "receipt-1")),
        GrowthScenarioOutcomeAxis(axisId="usage_settled", status="ready", exactRef=ref("SettlementRevision", "settlement-1")),
        GrowthScenarioOutcomeAxis(axisId="effect_mature", status="unknown", blocker=blocker("EFFECT_REVIEW_NOT_MATURE")),
        GrowthScenarioOutcomeAxis(axisId="memory_governed", status="blocked", blocker=blocker("MEMORY_CANDIDATE_GOVERNANCE_REQUIRED")),
    )


class Reader:
    def __init__(self, *, scope: TenantScope = SCOPE, binding: str | None = None, root_drift: bool = False, all_ready: bool = False) -> None:
        self.scope = scope
        self.binding = binding
        self.root_drift = root_drift
        self.all_ready = all_ready

    def read_scenario(self, scope: TenantScope, *, cutoff: datetime) -> GrowthScenarioObservation:
        root = ref("GrowthPlanRevision", "plan-1")
        stage_items = stages(ref("GrowthPlanRevision", "plan-drift") if self.root_drift else root)
        axis_items = tuple(GrowthScenarioOutcomeAxis(axisId=axis, status="ready", exactRef=ref("EvidencePack", axis.value)) for axis in GrowthScenarioOutcomeAxisId) if self.all_ready else axes()
        return GrowthScenarioObservation(scope=self.scope, cutoff=cutoff, root_plan_ref=root, scenario_binding_hash=self.binding or scenario_binding_hash(root, stage_items), stages=stage_items, ledger=GrowthScenarioConservationLedger(tasksExpected=6, tasksObserved=6, handoffsExpected=3, handoffsObserved=3, outcomesExpected=4, outcomesReady=4 if self.all_ready else 2, outcomesBlocked=0 if self.all_ready else 1, outcomesUnknown=0 if self.all_ready else 1), outcome_axes=axis_items)


def test_missing_root_returns_structured_blocked_contribution() -> None:
    result = EcommerceWorkshopGrowthScenario().read(scope=SCOPE, cutoff=CUTOFF)
    assert result.root_plan_ref is None
    assert [item.stage_id for item in result.stages] == list(GrowthScenarioStageId)
    assert [item.axis_id for item in result.outcome_axes] == list(GrowthScenarioOutcomeAxisId)
    assert result.commands.model_dump() == {"materialize": False, "dispatch": False, "publish": False, "promote_memory": False}
    assert result.external_effects_allowed is False


def test_exact_binding_keeps_effect_and_memory_axes_independent() -> None:
    result = EcommerceWorkshopGrowthScenario(reader=Reader()).read(scope=SCOPE, cutoff=CUTOFF)
    assert result.root_plan_ref and result.root_plan_ref.resource_type == "GrowthPlanRevision"
    assert all(item.status == "ready" for item in result.stages)
    assert [item.status for item in result.outcome_axes] == ["ready", "ready", "unknown", "blocked"]
    assert result.ledger.outcomes_ready == 2
    assert result.status == "blocked"


def test_cross_tenant_or_binding_drift_fails_closed_without_refs() -> None:
    other = TenantScope(org_id="dev-org", project_id="dev-project")
    tenant_result = EcommerceWorkshopGrowthScenario(reader=Reader(scope=other)).read(scope=SCOPE, cutoff=CUTOFF)
    binding_result = EcommerceWorkshopGrowthScenario(reader=Reader(binding="f" * 64)).read(scope=SCOPE, cutoff=CUTOFF)
    assert tenant_result.root_plan_ref is None
    assert tenant_result.blockers[0].code == "GROWTH_SCENARIO_SCOPE_OR_CUTOFF_DRIFT"
    assert binding_result.root_plan_ref is None
    assert binding_result.blockers[0].code == "GROWTH_SCENARIO_BINDING_DRIFT"


def test_root_stage_drift_and_all_ready_claims_return_structured_blocked_state() -> None:
    root_drift = EcommerceWorkshopGrowthScenario(reader=Reader(root_drift=True)).read(scope=SCOPE, cutoff=CUTOFF)
    all_ready = EcommerceWorkshopGrowthScenario(reader=Reader(all_ready=True)).read(scope=SCOPE, cutoff=CUTOFF)
    assert root_drift.root_plan_ref is None
    assert root_drift.blockers[0].code == "GROWTH_PLAN_ROOT_STAGE_DRIFT"
    assert all_ready.root_plan_ref is None
    assert all_ready.blockers[0].code == "GROWTH_SCENARIO_OPERATIONAL_AUTHORIZATION_REQUIRED"


def test_conservation_and_operational_claims_fail_closed() -> None:
    with pytest.raises(ValidationError):
        GrowthScenarioConservationLedger(tasksExpected=1, tasksObserved=2, handoffsExpected=0, handoffsObserved=0, outcomesExpected=4, outcomesReady=2, outcomesBlocked=1, outcomesUnknown=0)
    root = ref("GrowthPlanRevision", "plan-1")
    stage_items = stages()
    all_ready_axes = [GrowthScenarioOutcomeAxis(axisId=axis, status="ready", exactRef=ref("EvidencePack", axis.value)) for axis in GrowthScenarioOutcomeAxisId]
    with pytest.raises(ValidationError):
        GrowthScenarioContribution(rootPlanRef=root, scenarioBindingHash=scenario_binding_hash(root, stage_items), evaluatedAt=CUTOFF, stages=list(stage_items), ledger=GrowthScenarioConservationLedger(tasksExpected=0, tasksObserved=0, handoffsExpected=0, handoffsObserved=0, outcomesExpected=4, outcomesReady=4, outcomesBlocked=0, outcomesUnknown=0), outcomeAxes=all_ready_axes, blockers=[blocker("OPERATIONAL_AUTHORIZATION_REQUIRED")])
