from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_analyst_authority_contracts import (
    DecisionSummaryRevision,
    EcommerceEffectReviewRevision,
    GrowthPlanRevision,
    InsightRevision,
    TaskGraphRevision,
)
from aos_api.ecommerce_analyst_authority_store import canonical_hash

NOW = datetime(2026, 8, 25, tzinfo=UTC)
HASH = "a" * 64
TENANT = {"orgId": "org-org", "projectId": "dev-project"}


def ref(kind: str, identity: str, revision: int = 1) -> dict[str, object]:
    return {"resourceType": kind, "resourceId": identity, "revision": revision, "contentHash": HASH}


def insight(kind: str = "observation") -> dict[str, object]:
    return {"tenant": TENANT, "insightId": "insight-1", "revision": 1, "version": 1, "kind": kind, "summary": "GMV changed", "metricRefs": [ref("MetricObservationRevision", "metric-1")], "evidenceRefs": [ref("EvidenceBundleRevision", "evidence-1")], "methodRef": ref("MethodRevision", "method-1"), "evalRef": ref("EvalContractRevision", "eval-1"), "cutoffAt": NOW, "assumptions": ["same cutoff"], "uncertainty": "causality not established", "contentHash": HASH, "createdBy": "user:operator", "createdAt": NOW}


def plan(*, lifecycle: str = "approved") -> dict[str, object]:
    return {"tenant": TENANT, "planId": "plan-1", "revision": 1, "version": 1, "lifecycle": lifecycle, "decisionRef": ref("DecisionSummaryRevision", "decision-1"), "objective": "grow conversion", "constraints": ["no external effect"], "budget": "100.00", "expectedEffect": "+1%", "confidence": 0.6, "stopConditions": ["quality stale"], "items": [{"itemId": "item-1", "taskType": "analysis", "title": "inspect funnel", "objective": "find dropoff", "priority": 50, "eligible": True}], "approvedAt": NOW if lifecycle == "approved" else None, "contentHash": HASH, "createdBy": "user:operator", "createdAt": NOW}


@pytest.mark.parametrize("kind", ["observation", "correlation", "attribution", "causal_claim"])
def test_four_insight_kinds_are_explicit_and_valid(kind: str) -> None:
    assert InsightRevision.model_validate(insight(kind)).kind.value == kind


def test_insight_and_decision_reject_wrong_refs_and_private_chain_fields() -> None:
    wrong = insight()
    wrong["methodRef"] = ref("EvidenceBundleRevision", "wrong")
    with pytest.raises(ValidationError, match="methodRef"):
        InsightRevision.model_validate(wrong)
    decision = {"tenant": TENANT, "decisionId": "decision-1", "revision": 1, "version": 1, "insightRef": ref("InsightRevision", "insight-1"), "conclusion": "act carefully", "evidenceRefs": [ref("EvidenceBundleRevision", "evidence-1")], "attributionPath": ["metric", "insight", "decision"], "keyAssumptions": [], "counterEvidence": [], "alternativeExplanations": [], "uncertainty": "high", "contentHash": HASH, "createdBy": "user:operator", "createdAt": NOW, "reasoningChain": "must never persist"}
    with pytest.raises(ValidationError, match="reasoningChain"):
        DecisionSummaryRevision.model_validate(decision)


def test_growth_plan_requires_approved_timestamp_and_unique_items() -> None:
    assert GrowthPlanRevision.model_validate(plan()).lifecycle.value == "approved"
    invalid = plan()
    invalid["approvedAt"] = None
    with pytest.raises(ValidationError, match="approvedAt"):
        GrowthPlanRevision.model_validate(invalid)


def sales_weapon_method() -> dict[str, object]:
    sourced = lambda text: {"text": text, "evidenceRefs": [ref("EvidenceBundleRevision", "evidence-1")]}
    return {
        "productSourceKey": "niushop:goods:65",
        "productLabel": "栖月汇候选商品",
        "audienceHypothesis": sourced("可能适合有明确需求的人群，待验证"),
        "scenario": sourced("线下体验后的知识解释场景"),
        "fitFor": [sourced("需要先了解产品使用条件的人群")],
        "notFitFor": [sourced("无法确认使用条件的人群先转人工")],
        "proposedValueClaims": [sourced("可说明已核验的产品属性")],
        "unknownFacts": ["当前库存与真实贡献尚未核实"],
        "prohibitedClaims": ["不得承诺功效或保证收益"],
        "handoffCondition": "涉及个体适用性时交由真人核验",
        "channels": ["内部方案"],
        "timeWindow": "本轮内部评审前",
        "evidenceRefs": [ref("EvidenceBundleRevision", "evidence-1")],
        "sourceCutoffAt": NOW,
    }


def test_sales_weapon_method_is_hashed_plan_content_without_changing_legacy_shape() -> None:
    legacy = GrowthPlanRevision.model_validate(plan())
    legacy_payload = legacy.model_dump(mode="json", by_alias=True, exclude={"content_hash"})
    assert "salesWeaponMethod" not in legacy_payload
    payload = plan()
    payload["salesWeaponMethod"] = sales_weapon_method()
    current = GrowthPlanRevision.model_validate(payload)
    dumped = current.model_dump(mode="json", by_alias=True)
    assert dumped["salesWeaponMethod"]["fitFor"][0]["evidenceRefs"][0]["resourceId"] == "evidence-1"
    assert canonical_hash(current.model_dump(mode="json", by_alias=True, exclude={"content_hash"})) != canonical_hash(legacy_payload)
    assert current.sales_weapon_method is not None


@pytest.mark.parametrize("change", [
    {"fitFor": []},
    {"unknownFacts": []},
    {"prohibitedClaims": []},
    {"evidenceRefs": []},
    {"channels": []},
    {"timeWindow": ""},
    {"sourceCutoffAt": datetime(2026, 8, 25)},
    {"sourceCutoffAt": datetime(2026, 8, 26, tzinfo=UTC)},
])
def test_sales_weapon_method_rejects_incomplete_or_late_provenance(change: dict[str, object]) -> None:
    payload = plan()
    payload["salesWeaponMethod"] = {**sales_weapon_method(), **change}
    with pytest.raises(ValidationError):
        GrowthPlanRevision.model_validate(payload)


def test_sales_weapon_method_rejects_statement_outside_closed_evidence() -> None:
    payload = plan()
    method = sales_weapon_method()
    method["scenario"] = {"text": "外部主张", "evidenceRefs": [ref("EvidenceBundleRevision", "other")]}
    payload["salesWeaponMethod"] = method
    with pytest.raises(ValidationError):
        GrowthPlanRevision.model_validate(payload)


def test_task_graph_enforces_count_conservation_and_one_to_one_mapping() -> None:
    graph = {"tenant": TENANT, "graphId": "graph-1", "revision": 1, "version": 1, "planRef": ref("GrowthPlanRevision", "plan-1"), "eligiblePlanItemCount": 1, "canonicalTaskCount": 1, "mappings": [{"planItemId": "item-1", "taskRef": ref("Task", "task-1")}], "materializedAt": NOW, "contentHash": HASH, "createdBy": "user:operator", "createdAt": NOW}
    assert len(TaskGraphRevision.model_validate(graph).mappings) == 1
    graph["canonicalTaskCount"] = 0
    with pytest.raises(ValidationError, match="count conservation"):
        TaskGraphRevision.model_validate(graph)


def test_effect_review_does_not_turn_pending_or_unknown_into_zero_effect() -> None:
    effect = {"tenant": TENANT, "reviewId": "review-1", "revision": 1, "version": 1, "planRef": ref("GrowthPlanRevision", "plan-1"), "taskGraphRef": ref("TaskGraphRevision", "graph-1"), "actionReceiptRefs": [], "baseline": "week-1", "comparison": "week-2", "maturityWindow": "14d", "eligiblePopulation": "all eligible orders", "methodRef": ref("MethodRevision", "method-1"), "assumptions": [], "limitations": ["late data"], "counterfactualLimitations": ["no randomization"], "status": "pending", "effectValue": "0", "memoryCandidateRef": ref("MemoryCandidate", "candidate-1"), "contentHash": HASH, "createdBy": "user:operator", "createdAt": NOW}
    with pytest.raises(ValidationError, match="effectValue"):
        EcommerceEffectReviewRevision.model_validate(effect)
    effect["status"] = "mature"
    assert EcommerceEffectReviewRevision.model_validate(effect).memory_candidate_ref is not None
