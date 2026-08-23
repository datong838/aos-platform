from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from aos_api.aip_contracts import TenantContext
from aos_api.aip_ecommerce_growth_core_agents import SourceReadinessGateSnapshot
from aos_api.aip_ecommerce_growth_scenarios_sc07_sc09 import (
    ComplaintCaseGuard,
    CreatorLifecycleGuard,
    PriceGovernanceGuard,
    PriceTaskType,
    ProductRelation,
    R30ScenarioInput,
    R30ScenarioState,
    compile_sc07_sc09_acceptance,
)
from aos_api.aip_production_contracts import ExactRevisionRef


H = "f" * 64
T = datetime(2026, 8, 22, tzinfo=timezone.utc)
LOGICS = {
    "SC07": ["D02", "D03", *(f"G{i:02d}" for i in range(1, 7)), *(f"C{i:02d}" for i in range(1, 7)), *(f"A{i:02d}" for i in range(1, 7)), "S01", "S02", "P01"],
    "SC08": ["D01", "D03", "G01", "G02", "A01", "A03", "C06", "S01", "P03"],
    "SC09": [*(f"S{i:02d}" for i in range(1, 7)), "G02", "P01", "P02", "D01"],
}
CHAINS = {
    "SC07": ["CreatorRecruitmentPlanRevision", "CreatorCandidateBatchRevision", "CreatorOutreachDraftRevision", "CreatorCommercialOfferRevision", "CreatorContractRevision", "CreatorFulfillmentRevision", "CreatorPerformanceReviewRevision", "CreatorRelationshipPlanRevision"],
    "SC08": ["PriceMonitoringPolicyRevision", "ProductComparableDecisionRevision", "PriceObservationEvidenceRevision", "PriceObservationEvidenceRevision", "PriceNormalizationRevision", "PriceAnomalyCandidateRevision", "CompetitorBenchmarkRevision", "PriceActionDraftRevision"],
    "SC09": ["ServiceCaseRevision", "IdentityVerificationRevision", "ComplaintClassificationRevision", "ServiceReplyDraftRevision", "EscalationDecisionRevision", "PromiseBoundaryRevision", "ResolutionReceiptRevision", "EffectReviewRevision"],
}


def ref(kind: str, identity: str) -> ExactRevisionRef:
    return ExactRevisionRef(resource_type=kind, resource_id=identity, revision=1, content_hash=H)


def source(**changes: object) -> SourceReadinessGateSnapshot:
    values: dict[str, object] = {"evidence_pack_ref": ref("SourceReadinessEvidencePackRevision", "cutoff"), "status": "ready", "source_count": 12, "ready_count": 12, "checked_at": T, "cutoff_at": T, "fresh_until": T + timedelta(hours=2)}
    values.update(changes)
    return SourceReadinessGateSnapshot(**values)


def creator(**changes: object) -> CreatorLifecycleGuard:
    values: dict[str, object] = {"candidate_count": 100, "unique_count": 100, "duplicate_count": 0, "suppressed_count": 0, "expired_contact_count": 0, "authorized_channel": True, "outreach_sent": False, "contract_signed_claimed": False, "signature_receipt_present": False, "fulfillment_claimed": False, "fulfillment_receipt_present": False, "performance_final": False, "observation_window_closed": False, "relationship_contact_allowed": True}
    values.update(changes)
    return CreatorLifecycleGuard(**values)


def price(**changes: object) -> PriceGovernanceGuard:
    values: dict[str, object] = {"task_type": "exact_product_governance", "product_relation": "exact_sku", "governance_basis_present": True, "observation_count": 2, "independent_source_count": 2, "observation_contexts_aligned": True, "legal_conclusion_present": False, "external_action_executed": False, "price_changed": False, "malicious_order_or_refund": False}
    values.update(changes)
    return PriceGovernanceGuard(**values)


def complaint(**changes: object) -> ComplaintCaseGuard:
    values: dict[str, object] = {"identity_min_verified": True, "pii_tokenized": True, "classification_confidence": 0.9, "escalation_required": False, "escalated": False, "promise_within_authority": True, "external_reply_sent": False, "refund_executed": False, "resolution_claimed": False, "resolution_receipt_present": False, "aggregate_substitution": False}
    values.update(changes)
    return ComplaintCaseGuard(**values)


def scenario(sid: str, **changes: object) -> R30ScenarioInput:
    values: dict[str, object] = {
        "scenario_id": sid,
        "scenario_ref": ref("ScenarioRevision", f"ecommerce.{sid}"),
        "source_readiness": source(),
        "logic_refs": [ref("LogicGraphRevision", f"ecommerce.logic.{item}") for item in LOGICS[sid]],
        "chain_refs": [ref(kind, f"{sid.lower()}-{index}") for index, kind in enumerate(CHAINS[sid])],
        "task_run_ref": ref("TaskRunRevision", f"run-{sid.lower()}"),
        "receipt_ref": ref("ReceiptRevision", f"receipt-{sid.lower()}"),
        "lineage_ref": ref("LineageRevision", f"lineage-{sid.lower()}"),
        "effect_review_ref": ref("EffectReviewRevision", f"effect-{sid.lower()}"),
        "observed_cutoff": T,
        "fresh_until": T + timedelta(hours=2),
        "creator_guard": creator() if sid == "SC07" else None,
        "price_guard": price() if sid == "SC08" else None,
        "complaint_guard": complaint() if sid == "SC09" else None,
    }
    values.update(changes)
    return R30ScenarioInput(**values)


def compile_request(**changes: object):
    values = {"tenant": TenantContext(org_id="org-org", project_id="dev-project"), "requested_at": T + timedelta(minutes=30), "scenarios": [scenario("SC07"), scenario("SC08"), scenario("SC09")]}
    values.update(changes)
    return compile_sc07_sc09_acceptance(**values)


def codes(pack: object) -> set[str]:
    return {item.code for item in pack.blockers}


def test_three_independent_scenario_drafts() -> None:
    result = compile_request()
    assert result.state is R30ScenarioState.READY_FOR_REVIEW
    assert [item.scenario_id for item in result.evidence_packs] == ["SC07", "SC08", "SC09"]
    assert result.production_written is False


def test_negative_canary_and_source_readiness_fail_closed() -> None:
    items = [scenario(sid, source_readiness=source(status="blocked", ready_count=0)) for sid in LOGICS]
    result = compile_request(tenant=TenantContext(org_id="dev-org", project_id="dev-project"), scenarios=items)
    assert result.state is R30ScenarioState.BLOCKED
    assert all("R30_SOURCE_READINESS_NOT_READY" in codes(item) for item in result.evidence_packs)


@pytest.mark.parametrize(("changes", "code"), [({"candidate_count": 101}, "SC07_DAILY_CAPACITY_EXCEEDED"), ({"unique_count": 99}, "SC07_UNIQUE_COUNT_MISMATCH"), ({"duplicate_count": 1}, "SC07_DUPLICATE_CANDIDATE"), ({"suppressed_count": 1}, "SC07_SUPPRESSED_CANDIDATE"), ({"expired_contact_count": 1}, "SC07_EXPIRED_CONTACT"), ({"authorized_channel": False}, "SC07_CHANNEL_NOT_AUTHORIZED"), ({"outreach_sent": True}, "SC07_AUTOMATED_OUTREACH_FORBIDDEN"), ({"relationship_contact_allowed": False}, "SC07_RELATIONSHIP_CONTACT_BLOCKED")])
def test_sc07_candidate_and_outreach_guards(changes: dict[str, object], code: str) -> None:
    item = scenario("SC07", creator_guard=creator(**changes))
    assert code in codes(compile_request(scenarios=[item, scenario("SC08"), scenario("SC09")]).evidence_packs[0])


@pytest.mark.parametrize(("changes", "code"), [({"contract_signed_claimed": True}, "SC07_SIGNATURE_RECEIPT_MISSING"), ({"fulfillment_claimed": True}, "SC07_FULFILLMENT_RECEIPT_MISSING"), ({"performance_final": True}, "SC07_PERFORMANCE_WINDOW_OPEN")])
def test_sc07_lifecycle_claims_require_independent_evidence(changes: dict[str, object], code: str) -> None:
    item = scenario("SC07", creator_guard=creator(**changes))
    assert code in codes(compile_request(scenarios=[item, scenario("SC08"), scenario("SC09")]).evidence_packs[0])


def test_sc08_category_competitor_is_benchmark_only() -> None:
    item = scenario("SC08", price_guard=price(task_type="exact_product_governance", product_relation="category_competitor"))
    assert "SC08_COMPETITOR_CANNOT_ENTER_GOVERNANCE" in codes(compile_request(scenarios=[scenario("SC07"), item, scenario("SC09")]).evidence_packs[1])
    benchmark = scenario("SC08", price_guard=price(task_type="category_competitor_benchmark", product_relation="category_competitor", governance_basis_present=False))
    assert compile_request(scenarios=[scenario("SC07"), benchmark, scenario("SC09")]).evidence_packs[1].state is R30ScenarioState.READY_FOR_REVIEW


@pytest.mark.parametrize(("changes", "code"), [({"governance_basis_present": False}, "SC08_GOVERNANCE_BASIS_MISSING"), ({"observation_count": 1}, "SC08_TWO_OBSERVATIONS_REQUIRED"), ({"independent_source_count": 1}, "SC08_INDEPENDENT_EVIDENCE_MISSING"), ({"observation_contexts_aligned": False}, "SC08_OBSERVATION_CONTEXT_MISMATCH"), ({"legal_conclusion_present": True}, "SC08_LEGAL_CONCLUSION_FORBIDDEN"), ({"external_action_executed": True}, "SC08_EXTERNAL_ACTION_FORBIDDEN"), ({"price_changed": True}, "SC08_PRICE_CHANGE_FORBIDDEN"), ({"malicious_order_or_refund": True}, "SC08_MALICIOUS_ORDER_REFUND_FORBIDDEN")])
def test_sc08_price_governance_guards(changes: dict[str, object], code: str) -> None:
    item = scenario("SC08", price_guard=price(**changes))
    assert code in codes(compile_request(scenarios=[scenario("SC07"), item, scenario("SC09")]).evidence_packs[1])


@pytest.mark.parametrize(("changes", "code"), [({"identity_min_verified": False}, "SC09_IDENTITY_NOT_VERIFIED"), ({"pii_tokenized": False}, "SC09_RAW_PII_FORBIDDEN"), ({"escalation_required": True}, "SC09_ESCALATION_MISSING"), ({"promise_within_authority": False}, "SC09_PROMISE_OUT_OF_AUTHORITY"), ({"external_reply_sent": True}, "SC09_AUTOMATED_REPLY_FORBIDDEN"), ({"refund_executed": True}, "SC09_AUTOMATED_REFUND_FORBIDDEN"), ({"resolution_claimed": True}, "SC09_RESOLUTION_RECEIPT_MISSING"), ({"aggregate_substitution": True}, "SC09_CANNOT_SUBSTITUTE_AGGREGATE")])
def test_sc09_complaint_guards(changes: dict[str, object], code: str) -> None:
    item = scenario("SC09", complaint_guard=complaint(**changes))
    assert code in codes(compile_request(scenarios=[scenario("SC07"), scenario("SC08"), item]).evidence_packs[2])


@pytest.mark.parametrize("sid", ["SC07", "SC08", "SC09"])
def test_exact_logic_and_chain_fail_closed(sid: str) -> None:
    item = scenario(sid, logic_refs=scenario(sid).logic_refs[:-1], chain_refs=scenario(sid).chain_refs[:-1])
    result = compile_request(scenarios=[item, *(scenario(other) for other in LOGICS if other != sid)])
    pack = next(value for value in result.evidence_packs if value.scenario_id == sid)
    assert {"R30_LOGIC_SEQUENCE_INVALID", "R30_CHAIN_INVALID"}.issubset(codes(pack))


def test_no_side_effects() -> None:
    result = compile_request()
    assert result.pipeline_retried is False
    assert result.database_written is False
    assert result.provider_called is False
    assert result.action_executed is False
    assert result.memory_written is False


def test_manifest_matches_compiler_contract() -> None:
    path = Path(__file__).parents[4] / "bundles/solutions/ecommerce-growth/content/growth/sc07-sc09-acceptance.v1.json"
    manifest = json.loads(path.read_text())
    for scenario_id in ("SC07", "SC08", "SC09"):
        assert tuple(manifest["scenarios"][scenario_id]["logicIds"]) == tuple(LOGICS[scenario_id])
        assert tuple(manifest["scenarios"][scenario_id]["chain"]) == tuple(CHAINS[scenario_id])
    assert all(value is False for value in manifest["externalActions"].values())
