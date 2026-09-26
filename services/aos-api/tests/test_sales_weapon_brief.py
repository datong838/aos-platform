"""BG-03 draft semantics stay sourced and non-authoritative."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from ecommerce_growth.sales_weapon_brief import EvidenceBackedStatement, SalesWeaponBriefDraft
from ecommerce_growth.sdk_ports import ExactRef


NOW = datetime(2026, 9, 26, 8, tzinfo=UTC)
HASH = "sha256:" + "a" * 64


def ref(kind: str, identity: str) -> ExactRef:
    return ExactRef(kind, identity, 1, HASH)


PLAN = ref("GrowthPlanRevision", "plan-1")
DECISION = ref("DecisionSummaryRevision", "decision-1")
EVIDENCE = ref("EvidenceBundleRevision", "bundle-1")


def statement(value: str, evidence=EVIDENCE) -> EvidenceBackedStatement:
    return EvidenceBackedStatement(value, (evidence,))


def draft() -> SalesWeaponBriefDraft:
    return SalesWeaponBriefDraft(
        plan_ref=PLAN,
        decision_ref=DECISION,
        product_source_key="niushop:goods:65",
        product_label="栖月汇候选商品",
        audience_hypothesis=statement("可能适合有明确需求的人群，待验证"),
        scenario=statement("线下体验后的知识解释场景"),
        fit_for=(statement("需要先了解产品使用条件的人群"),),
        not_fit_for=(statement("无法确认使用条件的人群先转人工"),),
        proposed_value_claims=(statement("可说明已核验的产品属性"),),
        unknown_facts=("当前库存与真实贡献尚未核实",),
        prohibited_claims=("不得承诺功效或保证收益",),
        handoff_condition="涉及个体适用性时交由真人核验",
        evidence_refs=(EVIDENCE,),
        source_cutoff_at=NOW - timedelta(days=1),
    )


def test_single_product_business_method_is_a_draft_with_stable_payload():
    item = draft()
    item.validate_against(PLAN, DECISION, (EVIDENCE,), observed_at=NOW)
    payload = item.payload()
    assert payload["productSourceKey"] == "niushop:goods:65"
    assert payload["audienceHypothesis"]["evidenceRefs"][0]["resourceId"] == "bundle-1"
    assert payload["authority"] == "draft-only"
    assert payload == item.payload()


@pytest.mark.parametrize("change", [
    {"fit_for": ()}, {"not_fit_for": ()}, {"unknown_facts": ()},
    {"prohibited_claims": ()}, {"product_source_key": "  "},
    {"evidence_refs": (EVIDENCE, EVIDENCE)},
    {"source_cutoff_at": datetime(2026, 9, 25)},
    {"plan_ref": ref("Task", "plan-1")},
])
def test_missing_safety_or_wrong_exact_context_is_rejected(change):
    with pytest.raises(ValueError):
        replace(draft(), **change)


def test_external_or_duplicate_statement_source_is_rejected():
    with pytest.raises(ValueError):
        replace(draft(), scenario=statement("不受控外部事实", ref("EvidenceBundleRevision", "other")))
    with pytest.raises(ValueError):
        replace(draft(), fit_for=(statement("同一条"), statement("同一条")))


def test_authoritative_comparison_rejects_drift_and_future_cutoff():
    item = draft()
    with pytest.raises(ValueError):
        item.validate_against(ref("GrowthPlanRevision", "other"), DECISION, (EVIDENCE,), observed_at=NOW)
    with pytest.raises(ValueError):
        item.validate_against(PLAN, DECISION, (ref("EvidenceBundleRevision", "other"),), observed_at=NOW)
    with pytest.raises(ValueError):
        item.validate_against(PLAN, DECISION, (EVIDENCE,), observed_at=NOW - timedelta(days=2))
