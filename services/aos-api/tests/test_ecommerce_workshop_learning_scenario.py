"""W8-04 EffectReview-rooted governed learning scenario tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_learning_scenario import (
    EcommerceWorkshopLearningScenario,
    LearningScenarioObservation,
    learning_binding_hash,
)
from aos_api.ecommerce_workshop_learning_scenario_contracts import (
    LearningScenarioBlocker,
    LearningScenarioComposition,
    LearningScenarioContribution,
    LearningScenarioExactRef,
    LearningScenarioLedger,
    LearningScenarioOutcomeAxis,
    LearningScenarioOutcomeAxisId,
    LearningScenarioRoleBinding,
    LearningScenarioStage,
    LearningScenarioStageId,
)
from aos_api.tenant_scope import TenantScope


CUTOFF = datetime(2026, 8, 26, 5, tzinfo=UTC)
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")
HASH = "sha256:" + "a" * 64


def ref(resource_type: str, resource_id: str) -> LearningScenarioExactRef:
    return LearningScenarioExactRef(resourceType=resource_type, resourceId=resource_id, revision=1, contentHash=HASH)


def blocker(code: str) -> LearningScenarioBlocker:
    return LearningScenarioBlocker(code=code, dependency="workshop.learning-scenario", requiredAction="provide exact current evidence")


def composition() -> LearningScenarioComposition:
    return LearningScenarioComposition(
        atomicSkillRefs=[ref("SkillRevision", "review-outcomes"), ref("SkillRevision", "govern-knowledge")],
        logicRevisionRef=ref("LogicRevision", "effect-to-governed-knowledge"),
        roleBindings=[
            LearningScenarioRoleBinding(
                roleRef=ref("AgentTemplate", "analyst"),
                assigneeRef=ref("AgentInstance", "analyst-1"),
                skillBindingRef=ref("SkillBinding", "learning-binding-1"),
            )
        ],
    )


def stages(
    review: LearningScenarioExactRef | None = None,
    maturity: LearningScenarioExactRef | None = None,
) -> tuple[LearningScenarioStage, ...]:
    review = review or ref("EffectReviewRevision", "review-1")
    maturity = maturity or ref("EffectMaturityPolicyRevision", "maturity-1")
    refs = [
        [review],
        [maturity, ref("EffectMaturityDecision", "maturity-decision-1")],
        [ref("MemoryCandidateRevision", "candidate-1")],
        [ref("GovernanceApprovalRevision", "approval-1")],
        [ref("PromotionReceiptRevision", "promotion-1"), ref("WikiRevision", "wiki-1")],
        [ref("KnowledgeCitationRevision", "citation-1")],
        [],
    ]
    values: list[LearningScenarioStage] = []
    for index, stage in enumerate(LearningScenarioStageId):
        if stage is LearningScenarioStageId.REVOCATION_IMPACT:
            values.append(LearningScenarioStage(stageId=stage, status="unknown", contribution="等待撤销影响确认", blockers=[blocker("REVOCATION_IMPACT_REVIEW_REQUIRED")]))
        else:
            values.append(LearningScenarioStage(stageId=stage, status="ready", exactRefs=refs[index], contribution=f"stage {stage.value}"))
    return tuple(values)


def axes(*, all_ready: bool = False) -> tuple[LearningScenarioOutcomeAxis, ...]:
    result = [
        LearningScenarioOutcomeAxis(axisId=axis, status="ready", exactRef=ref("LearningOutcomeRevision", axis.value))
        for axis in LearningScenarioOutcomeAxisId
    ]
    if not all_ready:
        result[-1] = LearningScenarioOutcomeAxis(
            axisId=LearningScenarioOutcomeAxisId.REVOCATION_IMPACT_RECORDED,
            status="unknown",
            blocker=blocker("REVOCATION_IMPACT_REVIEW_REQUIRED"),
        )
    return tuple(result)


def ledger() -> LearningScenarioLedger:
    return LearningScenarioLedger(
        reviewsExpected=1,
        reviewsObserved=1,
        candidatesExpected=1,
        candidatesObserved=1,
        promotionsExpected=1,
        promotionsObserved=1,
        citationsExpected=1,
        citationsObserved=1,
        historicalExposures=2,
        retainedExposures=2,
        impactRefsExpected=1,
        impactRefsObserved=0,
    )


class Reader:
    def __init__(self, *, scope: TenantScope = SCOPE, binding: str | None = None, root_drift: bool = False, all_ready: bool = False) -> None:
        self.scope = scope
        self.binding = binding
        self.root_drift = root_drift
        self.all_ready = all_ready

    def read_scenario(self, scope: TenantScope, *, cutoff: datetime) -> LearningScenarioObservation:
        review = ref("EffectReviewRevision", "review-1")
        maturity = ref("EffectMaturityPolicyRevision", "maturity-1")
        layers = composition()
        stage_items = stages(ref("EffectReviewRevision", "review-drift") if self.root_drift else review, maturity)
        if self.all_ready:
            stage_items = stage_items[:-1] + (
                LearningScenarioStage(stageId=LearningScenarioStageId.REVOCATION_IMPACT, status="ready", exactRefs=[ref("RevocationImpactRevision", "impact-1")], contribution="impact ready"),
            )
        return LearningScenarioObservation(
            scope=self.scope,
            cutoff=cutoff,
            root_effect_review_ref=review,
            maturity_policy_ref=maturity,
            learning_binding_hash=self.binding or learning_binding_hash(review, maturity, layers, stage_items),
            composition=layers,
            stages=stage_items,
            ledger=ledger(),
            outcome_axes=axes(all_ready=self.all_ready),
        )


def test_missing_root_returns_structured_blocked_contribution() -> None:
    result = EcommerceWorkshopLearningScenario().read(scope=SCOPE, cutoff=CUTOFF)
    assert result.root_effect_review_ref is None
    assert [item.stage_id for item in result.stages] == list(LearningScenarioStageId)
    assert [item.axis_id for item in result.outcome_axes] == list(LearningScenarioOutcomeAxisId)
    assert result.commands.model_dump() == {
        "submit_candidate": False,
        "approve_candidate": False,
        "promote_candidate": False,
        "publish_wiki": False,
        "revoke_knowledge": False,
    }
    assert result.external_effects_allowed is False


def test_exact_binding_keeps_skill_logic_role_and_governance_axes_separate() -> None:
    result = EcommerceWorkshopLearningScenario(reader=Reader()).read(scope=SCOPE, cutoff=CUTOFF)
    assert result.root_effect_review_ref and result.root_effect_review_ref.resource_type == "EffectReviewRevision"
    assert result.composition and len(result.composition.atomic_skill_refs) == 2
    assert result.composition.logic_revision_ref.resource_type == "LogicRevision"
    assert result.composition.role_bindings[0].skill_binding_ref.resource_type == "SkillBinding"
    assert [item.status for item in result.outcome_axes] == ["ready", "ready", "ready", "ready", "unknown"]
    assert result.ledger.historical_exposures == result.ledger.retained_exposures == 2
    assert result.status == "blocked"


def test_cross_tenant_binding_and_root_drift_fail_closed_without_refs() -> None:
    other = TenantScope(org_id="dev-org", project_id="dev-project")
    tenant_result = EcommerceWorkshopLearningScenario(reader=Reader(scope=other)).read(scope=SCOPE, cutoff=CUTOFF)
    binding_result = EcommerceWorkshopLearningScenario(reader=Reader(binding="f" * 64)).read(scope=SCOPE, cutoff=CUTOFF)
    root_result = EcommerceWorkshopLearningScenario(reader=Reader(root_drift=True)).read(scope=SCOPE, cutoff=CUTOFF)
    assert tenant_result.blockers[0].code == "LEARNING_SCENARIO_SCOPE_OR_CUTOFF_DRIFT"
    assert binding_result.blockers[0].code == "LEARNING_SCENARIO_BINDING_DRIFT"
    assert root_result.blockers[0].code == "EFFECT_REVIEW_ROOT_STAGE_DRIFT"
    assert tenant_result.root_effect_review_ref is binding_result.root_effect_review_ref is root_result.root_effect_review_ref is None


def test_all_ready_operational_claim_is_replaced_by_explicit_gate_blocker() -> None:
    result = EcommerceWorkshopLearningScenario(reader=Reader(all_ready=True)).read(scope=SCOPE, cutoff=CUTOFF)
    assert result.root_effect_review_ref is None
    assert result.blockers[0].code == "LEARNING_SCENARIO_OPERATIONAL_AUTHORIZATION_REQUIRED"


def test_ledger_and_layer_aliasing_are_rejected() -> None:
    with pytest.raises(ValidationError):
        LearningScenarioLedger(
            reviewsExpected=1, reviewsObserved=1, candidatesExpected=1, candidatesObserved=1,
            promotionsExpected=1, promotionsObserved=1, citationsExpected=1, citationsObserved=1,
            historicalExposures=2, retainedExposures=1, impactRefsExpected=1, impactRefsObserved=0,
        )
    with pytest.raises(ValidationError):
        LearningScenarioComposition(
            atomicSkillRefs=[ref("LogicRevision", "not-a-skill")],
            logicRevisionRef=ref("LogicRevision", "logic-1"),
            roleBindings=composition().role_bindings,
        )


def test_fully_ready_contract_cannot_claim_operational_green() -> None:
    review = ref("EffectReviewRevision", "review-1")
    maturity = ref("EffectMaturityPolicyRevision", "maturity-1")
    layers = composition()
    stage_items = Reader(all_ready=True).read_scenario(SCOPE, cutoff=CUTOFF).stages
    with pytest.raises(ValidationError):
        LearningScenarioContribution(
            rootEffectReviewRef=review,
            maturityPolicyRef=maturity,
            learningBindingHash=learning_binding_hash(review, maturity, layers, stage_items),
            composition=layers,
            evaluatedAt=CUTOFF,
            stages=list(stage_items),
            ledger=ledger(),
            outcomeAxes=list(axes(all_ready=True)),
            blockers=[blocker("OPERATIONAL_AUTHORIZATION_REQUIRED")],
        )
