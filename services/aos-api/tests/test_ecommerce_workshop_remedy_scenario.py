"""W8-02 PriceCase-rooted remedy scenario fail-closed tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_remedy_scenario import EcommerceWorkshopRemedyScenario, RemedyScenarioObservation, remedy_binding_hash
from aos_api.ecommerce_workshop_remedy_scenario_contracts import RemedyScenarioConservationLedger, RemedyScenarioContribution, RemedyScenarioExactRef, RemedyScenarioOutcomeAxis, RemedyScenarioOutcomeAxisId, RemedyScenarioStage, RemedyScenarioStageId
from aos_api.tenant_scope import TenantScope


CUTOFF = datetime(2026, 8, 26, tzinfo=UTC)
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")
HASH = "sha256:" + "a" * 64
BLOCKER = {"code": "OPERATIONAL_GATE_REQUIRED", "dependency": "workshop.remedy-gate", "requiredAction": "provide exact authorized outcome"}


def ref(resource_type: str, resource_id: str) -> RemedyScenarioExactRef:
    return RemedyScenarioExactRef(resourceType=resource_type, resourceId=resource_id, revision=1, contentHash=HASH)


ROOT = ref("PriceCaseRevision", "price-case-1")


def stages(*, root: RemedyScenarioExactRef = ROOT, root_ready: bool = True) -> tuple[RemedyScenarioStage, ...]:
    result = []
    for stage_id in RemedyScenarioStageId:
        ready = stage_id in {RemedyScenarioStageId.PRICE_OBSERVATION, RemedyScenarioStageId.MATCH_DECISION} or (stage_id is RemedyScenarioStageId.PRICE_CASE and root_ready)
        result.append(RemedyScenarioStage(stageId=stage_id, status="ready" if ready else "blocked", exactRefs=[root] if stage_id is RemedyScenarioStageId.PRICE_CASE and ready else [ref("PriceAuthority", stage_id.value)] if ready else [], contribution=f"{stage_id.value} contribution", blockers=[] if ready else [BLOCKER]))
    return tuple(result)


def axes(*, all_ready: bool = False) -> tuple[RemedyScenarioOutcomeAxis, ...]:
    return tuple(RemedyScenarioOutcomeAxis(axisId=axis_id, status="ready" if all_ready else "blocked", exactRef=ref("OutcomeRevision", axis_id.value) if all_ready else None, blocker=None if all_ready else BLOCKER) for axis_id in RemedyScenarioOutcomeAxisId)


class Reader:
    def __init__(self, observation: RemedyScenarioObservation) -> None:
        self.observation = observation

    def read_scenario(self, scope, *, cutoff):
        return self.observation


def observation(*, scope: TenantScope = SCOPE, cutoff: datetime = CUTOFF, root: RemedyScenarioExactRef = ROOT, root_ready: bool = True, all_ready: bool = False, binding_drift: bool = False) -> RemedyScenarioObservation:
    scenario_stages = stages(root=root, root_ready=root_ready)
    scenario_axes = axes(all_ready=all_ready)
    if all_ready:
        scenario_stages = tuple(RemedyScenarioStage(stageId=item.stage_id, status="ready", exactRefs=item.exact_refs or [ref("StageRevision", item.stage_id.value)], contribution=item.contribution) for item in scenario_stages)
    binding = remedy_binding_hash(root, scenario_stages)
    return RemedyScenarioObservation(scope=scope, cutoff=cutoff, root_case_ref=root, remedy_binding_hash="0" * 64 if binding_drift else binding, stages=scenario_stages, ledger=RemedyScenarioConservationLedger(affectedOrdersExpected=3, affectedOrdersObserved=2, eligibleCustomersExpected=2, eligibleCustomersObserved=1, actionsExpected=5, actionsReady=0 if not all_ready else 5, actionsBlocked=5 if not all_ready else 0, actionsUnknown=0), outcome_axes=scenario_axes)


def test_missing_root_is_structured_blocked_without_contact_or_commands() -> None:
    result = EcommerceWorkshopRemedyScenario().read(scope=SCOPE, cutoff=CUTOFF)
    assert result.status == "blocked" and result.root_case_ref is None
    assert len(result.stages) == 9 and len(result.outcome_axes) == 5
    assert result.protected_contact_resolved is False and result.external_effects_allowed is False
    assert result.commands.model_dump() == {"reprice": False, "refund_or_compensate": False, "send_message": False, "resolve_case": False}


def test_exact_binding_preserves_independent_outcome_axes_and_ledger() -> None:
    source = observation()
    result = EcommerceWorkshopRemedyScenario(reader=Reader(source)).read(scope=SCOPE, cutoff=CUTOFF)
    assert result.root_case_ref == ROOT and result.remedy_binding_hash == source.remedy_binding_hash
    assert [item.axis_id for item in result.outcome_axes] == list(RemedyScenarioOutcomeAxisId)
    assert result.ledger.affected_orders_expected == 3 and result.ledger.eligible_customers_observed == 1
    assert len(result.blockers) == 11


@pytest.mark.parametrize(
    ("source", "code"),
    [
        (observation(scope=TenantScope(org_id="dev-org", project_id="dev-project")), "REMEDY_SCENARIO_SCOPE_OR_CUTOFF_DRIFT"),
        (observation(binding_drift=True), "REMEDY_SCENARIO_BINDING_DRIFT"),
        (observation(root_ready=False), "PRICE_CASE_ROOT_STAGE_DRIFT"),
        (observation(all_ready=True), "REMEDY_SCENARIO_OPERATIONAL_AUTHORIZATION_REQUIRED"),
    ],
)
def test_reader_drift_and_all_ready_claims_fail_closed(source: RemedyScenarioObservation, code: str) -> None:
    result = EcommerceWorkshopRemedyScenario(reader=Reader(source)).read(scope=SCOPE, cutoff=CUTOFF)
    assert result.root_case_ref is None and result.blockers[0].code == code
    assert result.commands.send_message is False


def test_contract_rejects_denominator_drift_operational_ready_and_pii() -> None:
    with pytest.raises(ValidationError, match="conserve"):
        RemedyScenarioConservationLedger(affectedOrdersExpected=1, affectedOrdersObserved=1, eligibleCustomersExpected=1, eligibleCustomersObserved=1, actionsExpected=5, actionsReady=1, actionsBlocked=1, actionsUnknown=1)
    source = observation(all_ready=True)
    with pytest.raises(ValidationError, match="cannot claim operational ready"):
        RemedyScenarioContribution(rootCaseRef=ROOT, remedyBindingHash=source.remedy_binding_hash, evaluatedAt=CUTOFF, stages=list(source.stages), ledger=source.ledger, outcomeAxes=list(source.outcome_axes), blockers=[BLOCKER])
    with pytest.raises(ValidationError):
        RemedyScenarioExactRef(resourceType="PriceCaseRevision", resourceId="case", revision=1, contentHash=HASH, mobile="redacted-test-value")
