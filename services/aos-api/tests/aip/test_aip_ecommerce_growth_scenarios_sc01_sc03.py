from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from aos_api.aip_contracts import TenantContext
from aos_api.aip_ecommerce_growth_core_agents import SourceReadinessGateSnapshot
from aos_api.aip_ecommerce_growth_scenarios_sc01_sc03 import (
    DecisionState,
    ScenarioAcceptanceInput,
    ScenarioAcceptanceState,
    ScenarioGuardSnapshot,
    ScenarioLogicStage,
    compile_sc01_sc03_acceptance,
)
from aos_api.aip_production_contracts import ExactRevisionRef


HASH = "c" * 64
CUTOFF = datetime(2026, 8, 22, 0, 0, tzinfo=timezone.utc)
LOGICS = {
    "SC01": ["D02", "D03", *(f"C{i:02d}" for i in range(1, 9)), *(f"G{i:02d}" for i in range(1, 7)), "S01", "S06"],
    "SC02": ["D01", "D03", *(f"P{i:02d}" for i in range(2, 6)), "C02", "C03", "G02", "G04", "S02"],
    "SC03": [*(f"S{i:02d}" for i in range(1, 7)), "D01", "D06", "C06", "C08", "G03", "G05", "A05"],
}
CHAINS = {
    "SC01": ["ContentArtifactRevision", "LeadSignalRevision", "ConsultationSessionRevision", "RecommendationRevision", "OrderFeedbackRevision", "AttributionRevision"],
    "SC02": ["CustomerLiteProjectionRevision", "ContactPolicyRevision", "ConsentEventRevision", "ContentDraftRevision", "RecommendationRevision", "OrderFeedbackRevision", "EffectReviewRevision"],
    "SC03": ["ServiceCaseAggregateRevision", "ProblemImpactRevision", "ContentCorrectionDraftRevision", "RecommendationCorrectionDraftRevision", "PromotionPauseProposalRevision", "MetricValidationRevision"],
}


def ref(kind: str, identity: str) -> ExactRevisionRef:
    return ExactRevisionRef(resource_type=kind, resource_id=identity, revision=1, content_hash=HASH)


def source(**changes: object) -> SourceReadinessGateSnapshot:
    values: dict[str, object] = {
        "evidence_pack_ref": ref("SourceReadinessEvidencePackRevision", "p01-p12-cutoff"),
        "status": "ready",
        "source_count": 12,
        "ready_count": 12,
        "checked_at": CUTOFF,
        "cutoff_at": CUTOFF,
        "fresh_until": CUTOFF + timedelta(hours=2),
    }
    values.update(changes)
    return SourceReadinessGateSnapshot(**values)


def guard(**changes: object) -> ScenarioGuardSnapshot:
    values: dict[str, object] = {
        "consent": "allow",
        "channel": "allow",
        "frequency_cap": "allow",
        "opt_out": "block",
        "complaint_guard": "allow",
        "aggregation_count": 3,
        "single_case_substitution": False,
    }
    values.update(changes)
    return ScenarioGuardSnapshot(**values)


def stages(scenario_id: str) -> list[ScenarioLogicStage]:
    return [
        ScenarioLogicStage(order=i, logic_id=logic_id, logic_ref=ref("LogicGraphRevision", f"ecommerce.logic.{logic_id}"))
        for i, logic_id in enumerate(LOGICS[scenario_id], start=1)
    ]


def scenario(scenario_id: str, **changes: object) -> ScenarioAcceptanceInput:
    values: dict[str, object] = {
        "scenario_id": scenario_id,
        "scenario_ref": ref("ScenarioRevision", f"ecommerce.{scenario_id}"),
        "source_readiness": source(),
        "task_ref": ref("TaskRevision", f"task-{scenario_id.lower()}"),
        "task_run_ref": ref("TaskRunRevision", f"run-{scenario_id.lower()}"),
        "logic_stages": stages(scenario_id),
        "handoff_refs": [ref("HandoffRevision", f"handoff-{scenario_id.lower()}")],
        "receipt_refs": [ref("ReceiptRevision", f"receipt-{scenario_id.lower()}")],
        "lineage_ref": ref("LineageRevision", f"lineage-{scenario_id.lower()}"),
        "effect_review_ref": ref("EffectReviewRevision", f"effect-{scenario_id.lower()}"),
        "chain_refs": [ref(kind, f"{scenario_id.lower()}-{i}") for i, kind in enumerate(CHAINS[scenario_id], start=1)],
        "guard": guard(),
        "window_start": CUTOFF,
        "window_end": CUTOFF + timedelta(hours=1),
        "observed_cutoff": CUTOFF,
        "fresh_until": CUTOFF + timedelta(hours=2),
        "source_labels": ["niushop-production", "aos-authority"],
        "external_action_state": "draft",
    }
    values.update(changes)
    return ScenarioAcceptanceInput(**values)


def compile_request(**changes: object):
    values = {
        "tenant": TenantContext(org_id="org-org", project_id="dev-project"),
        "requested_at": CUTOFF + timedelta(minutes=30),
        "scenarios": [scenario("SC01"), scenario("SC02"), scenario("SC03")],
    }
    values.update(changes)
    return compile_sc01_sc03_acceptance(**values)


def codes(pack: object) -> set[str]:
    return {item.code for item in pack.blockers}


def test_three_scenarios_produce_independent_replayable_drafts() -> None:
    result = compile_request()
    assert result.state is ScenarioAcceptanceState.READY_FOR_REVIEW
    assert [item.scenario_id for item in result.evidence_packs] == ["SC01", "SC02", "SC03"]
    assert len({item.replay_digest for item in result.evidence_packs}) == 3
    assert all(item.external_action_authorized is False for item in result.evidence_packs)
    assert result.production_written is False


def test_negative_canary_is_blocked_and_side_effect_free() -> None:
    result = compile_request(
        tenant=TenantContext(org_id="dev-org", project_id="dev-project"),
        scenarios=[scenario(sid, source_readiness=source(status="blocked", ready_count=0)) for sid in LOGICS],
    )
    assert result.state is ScenarioAcceptanceState.BLOCKED
    assert result.production_written is False


@pytest.mark.parametrize("scenario_id", ["SC01", "SC02", "SC03"])
def test_source_readiness_failure_blocks_each_scenario(scenario_id: str) -> None:
    item = scenario(scenario_id, source_readiness=source(status="failed", ready_count=10))
    result = compile_request(scenarios=[item, *(scenario(sid) for sid in LOGICS if sid != scenario_id)])
    pack = next(value for value in result.evidence_packs if value.scenario_id == scenario_id)
    assert "SC_SOURCE_READINESS_NOT_READY" in codes(pack)


def test_stale_source_and_scenario_window_are_blocked() -> None:
    item = scenario("SC01", source_readiness=source(fresh_until=CUTOFF + timedelta(minutes=1)))
    pack = compile_request(scenarios=[item, scenario("SC02"), scenario("SC03")]).evidence_packs[0]
    assert "SC_SOURCE_READINESS_STALE" in codes(pack)


def test_cutoff_mismatch_is_blocked() -> None:
    item = scenario("SC01", observed_cutoff=CUTOFF + timedelta(minutes=1))
    pack = compile_request(scenarios=[item, scenario("SC02"), scenario("SC03")]).evidence_packs[0]
    assert "SC_CUTOFF_MISMATCH" in codes(pack)


@pytest.mark.parametrize("scenario_id", ["SC01", "SC02", "SC03"])
def test_logic_sequence_is_exact(scenario_id: str) -> None:
    item = scenario(scenario_id, logic_stages=list(reversed(stages(scenario_id))))
    result = compile_request(scenarios=[item, *(scenario(sid) for sid in LOGICS if sid != scenario_id)])
    pack = next(value for value in result.evidence_packs if value.scenario_id == scenario_id)
    assert "SC_LOGIC_SEQUENCE_INVALID" in codes(pack)


@pytest.mark.parametrize("scenario_id", ["SC01", "SC02", "SC03"])
def test_missing_chain_stage_is_blocked(scenario_id: str) -> None:
    item = scenario(scenario_id, chain_refs=scenario(scenario_id).chain_refs[:-1])
    result = compile_request(scenarios=[item, *(scenario(sid) for sid in LOGICS if sid != scenario_id)])
    pack = next(value for value in result.evidence_packs if value.scenario_id == scenario_id)
    assert "SC_CHAIN_INCOMPLETE" in codes(pack)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("consent", "unknown", "SC02_CONSENT_BLOCKED"),
        ("channel", "block", "SC02_CHANNEL_BLOCKED"),
        ("frequency_cap", "unknown", "SC02_FREQUENCY_BLOCKED"),
        ("opt_out", "allow", "SC02_OPT_OUT_BLOCKED"),
        ("complaint_guard", "block", "SC02_COMPLAINT_GUARD_BLOCKED"),
    ],
)
def test_sc02_contact_and_complaint_guards(field: str, value: str, code: str) -> None:
    item = scenario("SC02", guard=guard(**{field: value}))
    pack = compile_request(scenarios=[scenario("SC01"), item, scenario("SC03")]).evidence_packs[1]
    assert code in codes(pack)


def test_sc03_requires_aggregate_not_single_case_substitution() -> None:
    item = scenario("SC03", guard=guard(aggregation_count=1, single_case_substitution=True))
    pack = compile_request(scenarios=[scenario("SC01"), scenario("SC02"), item]).evidence_packs[2]
    assert "SC03_AGGREGATION_INSUFFICIENT" in codes(pack)
    assert "SC03_SINGLE_CASE_SUBSTITUTION" in codes(pack)


@pytest.mark.parametrize("state", ["executed", "sent", "paused", "confirmed"])
def test_unapproved_external_action_claim_is_rejected(state: str) -> None:
    with pytest.raises(ValidationError):
        scenario("SC01", external_action_state=state)


@pytest.mark.parametrize("label", ["mock-data", "fixture", "sample-row", "fake-provider", "placeholder"])
def test_non_real_source_labels_are_rejected(label: str) -> None:
    with pytest.raises(ValidationError):
        scenario("SC01", source_labels=[label])


def test_duplicate_or_missing_scenario_is_rejected() -> None:
    with pytest.raises(ValueError):
        compile_request(scenarios=[scenario("SC01"), scenario("SC01"), scenario("SC03")])


def test_exact_authority_types_are_validated() -> None:
    with pytest.raises(ValidationError):
        scenario("SC01", task_ref=ref("ArtifactRevision", "wrong"))


def test_compilation_has_no_side_effects() -> None:
    result = compile_request()
    assert result.database_written is False
    assert result.provider_called is False
    assert result.action_executed is False
    assert result.memory_written is False
    assert result.pipeline_retried is False
