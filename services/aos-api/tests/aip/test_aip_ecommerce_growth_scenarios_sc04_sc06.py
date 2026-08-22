from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from aos_api.aip_contracts import TenantContext
from aos_api.aip_ecommerce_growth_core_agents import SourceReadinessGateSnapshot
from aos_api.aip_ecommerce_growth_scenarios_sc04_sc06 import (
    PatrolOutcome,
    R29ScenarioInput,
    R29ScenarioState,
    Scenario04Guard,
    Scenario05Guard,
    Scenario06Guard,
    compile_sc04_sc06_acceptance,
)
from aos_api.aip_production_contracts import ExactRevisionRef


H = "e" * 64
T = datetime(2026, 8, 22, tzinfo=timezone.utc)
LOGICS = {
    "SC04": [*(f"A{i:02d}" for i in range(1, 7)), *(f"D{i:02d}" for i in range(3, 7)), *(f"C{i:02d}" for i in range(2, 7)), "P03", "S01"],
    "SC05": ["D02", "D03", *(f"C{i:02d}" for i in range(1, 7)), "G02", "G03", "G04", "A01", "A04", "S01"],
    "SC06": [*(f"D{i:02d}" for i in range(1, 7))],
}
CHAINS = {
    "SC04": ["CampaignPlanRevision", "BudgetEnvelopeRevision", "CostSnapshotRevision", "PriceSnapshotRevision", "InventorySnapshotRevision", "FulfillmentSnapshotRevision", "ExperimentRevision", "StopPolicyRevision", "MetricValidationRevision"],
    "SC05": ["ProductFactsRevision", "ContentAssetRevision", "CopyrightEvidenceRevision", "PlatformRuleReviewRevision", "PublishDraftRevision"],
    "SC06": ["PatrolTaskRevision", "CheckpointRevision", "CheckpointReceiptRevision", "EffectReviewRevision", "MemoryCandidateRevision"],
}


def ref(kind: str, identity: str) -> ExactRevisionRef:
    return ExactRevisionRef(resource_type=kind, resource_id=identity, revision=1, content_hash=H)


def source(**changes: object) -> SourceReadinessGateSnapshot:
    values: dict[str, object] = {"evidence_pack_ref": ref("SourceReadinessEvidencePackRevision", "cutoff"), "status": "ready", "source_count": 12, "ready_count": 12, "checked_at": T, "cutoff_at": T, "fresh_until": T + timedelta(hours=2)}
    values.update(changes)
    return SourceReadinessGateSnapshot(**values)


def sc04(**changes: object) -> Scenario04Guard:
    values: dict[str, object] = {"budget_limit": 1000, "budget_requested": 800, "margin_floor": 0.2, "projected_margin": 0.3, "price_ready": True, "inventory_ready": True, "fulfillment_ready": True, "capacity_ready": True, "experiment_frozen": True, "assignment_clean": True, "stop_triggered": False, "pause_proposal_present": False, "pause_executed": False}
    values.update(changes)
    return Scenario04Guard(**values)


def sc05(**changes: object) -> Scenario05Guard:
    values: dict[str, object] = {"product_facts_fresh": True, "asset_reviewed": True, "copyright_evidence_present": True, "platform_rules_passed": True, "publish_authorized": False, "platform_receipt_present": False}
    values.update(changes)
    return Scenario05Guard(**values)


def sc06(**changes: object) -> Scenario06Guard:
    values: dict[str, object] = {"outcome": "no_action", "recommendation_count": 0, "pause_requested": False, "resume_requested": False, "pause_checkpoint_ref": None, "resume_checkpoint_ref": None, "memory_promoted": False}
    values.update(changes)
    return Scenario06Guard(**values)


def scenario(sid: str, **changes: object) -> R29ScenarioInput:
    values: dict[str, object] = {
        "scenario_id": sid,
        "scenario_ref": ref("ScenarioRevision", f"ecommerce.{sid}"),
        "source_readiness": source(),
        "logic_refs": [ref("LogicGraphRevision", f"ecommerce.logic.{x}") for x in LOGICS[sid]],
        "chain_refs": [ref(kind, f"{sid.lower()}-{i}") for i, kind in enumerate(CHAINS[sid])],
        "task_run_ref": ref("TaskRunRevision", f"run-{sid.lower()}"),
        "lineage_ref": ref("LineageRevision", f"lineage-{sid.lower()}"),
        "effect_review_ref": ref("EffectReviewRevision", f"effect-{sid.lower()}"),
        "observed_cutoff": T,
        "fresh_until": T + timedelta(hours=2),
        "promotion_guard": sc04() if sid == "SC04" else None,
        "product_guard": sc05() if sid == "SC05" else None,
        "patrol_guard": sc06() if sid == "SC06" else None,
    }
    values.update(changes)
    return R29ScenarioInput(**values)


def compile_request(**changes: object):
    values = {"tenant": TenantContext(org_id="org-org", project_id="dev-project"), "requested_at": T + timedelta(minutes=30), "scenarios": [scenario("SC04"), scenario("SC05"), scenario("SC06")]}
    values.update(changes)
    return compile_sc04_sc06_acceptance(**values)


def codes(pack: object) -> set[str]:
    return {x.code for x in pack.blockers}


def test_three_scenarios_are_independently_reviewable() -> None:
    result = compile_request()
    assert result.state is R29ScenarioState.READY_FOR_REVIEW
    assert [x.scenario_id for x in result.evidence_packs] == ["SC04", "SC05", "SC06"]
    assert result.evidence_packs[2].patrol_outcome is PatrolOutcome.NO_ACTION
    assert result.production_written is False


def test_negative_canary_is_blocked() -> None:
    result = compile_request(tenant=TenantContext(org_id="dev-org", project_id="dev-project"), scenarios=[scenario(sid, source_readiness=source(status="blocked", ready_count=0)) for sid in LOGICS])
    assert result.state is R29ScenarioState.BLOCKED


@pytest.mark.parametrize(("changes", "code"), [({"budget_requested": 1001}, "SC04_BUDGET_EXCEEDED"), ({"projected_margin": 0.1}, "SC04_MARGIN_BELOW_FLOOR"), ({"price_ready": False}, "SC04_PRICE_NOT_READY"), ({"inventory_ready": False}, "SC04_INVENTORY_NOT_READY"), ({"fulfillment_ready": False}, "SC04_FULFILLMENT_NOT_READY"), ({"capacity_ready": False}, "SC04_CAPACITY_NOT_READY"), ({"experiment_frozen": False}, "SC04_EXPERIMENT_NOT_FROZEN"), ({"assignment_clean": False}, "SC04_ASSIGNMENT_CONTAMINATED")])
def test_sc04_guards(changes: dict[str, object], code: str) -> None:
    item = scenario("SC04", promotion_guard=sc04(**changes))
    assert code in codes(compile_request(scenarios=[item, scenario("SC05"), scenario("SC06")]).evidence_packs[0])


def test_stop_trigger_requires_pause_proposal_but_never_execution() -> None:
    blocked = scenario("SC04", promotion_guard=sc04(stop_triggered=True))
    assert "SC04_PAUSE_PROPOSAL_MISSING" in codes(compile_request(scenarios=[blocked, scenario("SC05"), scenario("SC06")]).evidence_packs[0])
    allowed = scenario("SC04", promotion_guard=sc04(stop_triggered=True, pause_proposal_present=True))
    pack = compile_request(scenarios=[allowed, scenario("SC05"), scenario("SC06")]).evidence_packs[0]
    assert pack.state is R29ScenarioState.READY_FOR_REVIEW
    assert pack.external_action_authorized is False


def test_pause_execution_claim_is_blocked() -> None:
    item = scenario("SC04", promotion_guard=sc04(pause_executed=True))
    assert "SC04_UNAUTHORIZED_PAUSE_EXECUTION" in codes(compile_request(scenarios=[item, scenario("SC05"), scenario("SC06")]).evidence_packs[0])


@pytest.mark.parametrize(("changes", "code"), [({"product_facts_fresh": False}, "SC05_PRODUCT_FACTS_STALE"), ({"asset_reviewed": False}, "SC05_ASSET_NOT_REVIEWED"), ({"copyright_evidence_present": False}, "SC05_COPYRIGHT_EVIDENCE_MISSING"), ({"platform_rules_passed": False}, "SC05_PLATFORM_RULES_BLOCKED"), ({"publish_authorized": True}, "SC05_PUBLISH_NOT_AUTHORIZED"), ({"platform_receipt_present": True}, "SC05_FAKE_PLATFORM_RECEIPT")])
def test_sc05_guards(changes: dict[str, object], code: str) -> None:
    item = scenario("SC05", product_guard=sc05(**changes))
    assert code in codes(compile_request(scenarios=[scenario("SC04"), item, scenario("SC06")]).evidence_packs[1])


def test_sc06_no_action_is_a_valid_result() -> None:
    pack = compile_request().evidence_packs[2]
    assert pack.state is R29ScenarioState.READY_FOR_REVIEW
    assert pack.patrol_outcome is PatrolOutcome.NO_ACTION


def test_sc06_no_action_cannot_contain_forced_recommendation() -> None:
    item = scenario("SC06", patrol_guard=sc06(recommendation_count=1))
    assert "SC06_FORCED_OPPORTUNITY" in codes(compile_request(scenarios=[scenario("SC04"), scenario("SC05"), item]).evidence_packs[2])


def test_sc06_pause_resume_checkpoints_are_paired() -> None:
    item = scenario("SC06", patrol_guard=sc06(pause_requested=True))
    assert "SC06_PAUSE_CHECKPOINT_MISSING" in codes(compile_request(scenarios=[scenario("SC04"), scenario("SC05"), item]).evidence_packs[2])
    item = scenario("SC06", patrol_guard=sc06(resume_requested=True, pause_checkpoint_ref=ref("CheckpointRevision", "pause")))
    assert "SC06_RESUME_CHECKPOINT_MISSING" in codes(compile_request(scenarios=[scenario("SC04"), scenario("SC05"), item]).evidence_packs[2])


def test_sc06_memory_cannot_be_auto_promoted() -> None:
    item = scenario("SC06", patrol_guard=sc06(memory_promoted=True))
    assert "SC06_MEMORY_AUTO_PROMOTION_FORBIDDEN" in codes(compile_request(scenarios=[scenario("SC04"), scenario("SC05"), item]).evidence_packs[2])


@pytest.mark.parametrize("sid", ["SC04", "SC05", "SC06"])
def test_source_readiness_and_exact_chain_fail_closed(sid: str) -> None:
    item = scenario(sid, source_readiness=source(status="failed", ready_count=10), chain_refs=scenario(sid).chain_refs[:-1])
    result = compile_request(scenarios=[item, *(scenario(x) for x in LOGICS if x != sid)])
    pack = next(x for x in result.evidence_packs if x.scenario_id == sid)
    assert {"R29_SOURCE_READINESS_NOT_READY", "R29_CHAIN_INVALID"}.issubset(codes(pack))


def test_no_side_effects() -> None:
    result = compile_request()
    assert result.pipeline_retried is False
    assert result.database_written is False
    assert result.action_executed is False
    assert result.provider_called is False


def test_installable_manifest_matches_compiler_contract() -> None:
    manifest_path = (
        Path(__file__).parents[4]
        / "bundles/solutions/ecommerce-growth/content/growth/sc04-sc06-acceptance.v1.json"
    )
    manifest = json.loads(manifest_path.read_text())
    for scenario_id in ("SC04", "SC05", "SC06"):
        assert tuple(manifest["scenarios"][scenario_id]["logicIds"]) == tuple(LOGICS[scenario_id])
        assert tuple(manifest["scenarios"][scenario_id]["chain"]) == tuple(CHAINS[scenario_id])
    assert manifest["realInputPolicy"]["requiredTenant"] == "org-org/dev-project"
    assert manifest["realInputPolicy"]["negativeCanary"] == "dev-org/dev-project"
    assert all(value is False for value in manifest["externalActions"].values())
