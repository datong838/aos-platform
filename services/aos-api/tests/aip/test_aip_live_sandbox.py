from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from aos_api.aip_contracts import ArtifactRef
from aos_api.aip_live_sandbox import (
    DirectorAction,
    KnowledgeState,
    KillLevel,
    LiveAgentRole,
    LiveAgentStage,
    LiveInteractionSignal,
    LiveLatencyBudget,
    LiveReadinessObservation,
    LiveSandboxManifest,
    assess_live_sandbox_readiness,
    decide_live_interaction,
    escalate_kill_level,
)
from aos_api.aip_production_contracts import ExactRevisionRef, MutableAuthorityRef


HASH = "a" * 64
NOW = datetime(2026, 8, 22, 5, 0, tzinfo=timezone.utc)


def exact(kind: str, identity: str) -> ExactRevisionRef:
    return ExactRevisionRef(
        resource_type=kind,
        resource_id=identity,
        revision=1,
        content_hash=HASH,
    )


def mutable(kind: str, identity: str) -> MutableAuthorityRef:
    return MutableAuthorityRef(resource_type=kind, resource_id=identity, version=1)


def artifact(kind: str, identity: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=identity,
        artifact_type=kind,
        revision="1",
        content_hash=HASH,
    )


def stages() -> list[LiveAgentStage]:
    rows = (
        (LiveAgentRole.DANMU_UNDERSTANDING, "SanitizedDanmuEnvelope", "DanmuUnderstandingArtifact"),
        (LiveAgentRole.KNOWLEDGE_RETRIEVAL, "DanmuUnderstandingArtifact", "LiveKnowledgeMatchArtifact"),
        (LiveAgentRole.SCRIPT_DRAFTING, "LiveKnowledgeMatchArtifact", "LiveScriptDraftArtifact"),
        (LiveAgentRole.SAFETY_FILTERING, "LiveScriptDraftArtifact", "LiveSafetyDecisionArtifact"),
        (LiveAgentRole.DIRECTOR_CONTROL, "LiveSafetyDecisionArtifact", "LiveDirectorDecisionArtifact"),
    )
    return [
        LiveAgentStage(
            order=index,
            role=role,
            capability_ref=exact("CapabilityRevision", f"live-{role.value}"),
            input_artifact_type=input_kind,
            output_artifact_type=output_kind,
        )
        for index, (role, input_kind, output_kind) in enumerate(rows, start=1)
    ]


def manifest(**overrides: object) -> LiveSandboxManifest:
    values: dict[str, object] = {
        "duration_seconds": 300,
        "live_plan_ref": artifact("live_plan", "plan-1"),
        "knowledge_snapshot_ref": artifact("live_knowledge_snapshot", "knowledge-1"),
        "digital_human_profile_ref": exact("DigitalHumanProfileRevision", "profile-1"),
        "factuality_eval_ref": exact("EvalReportRevision", "eval-factuality"),
        "safety_eval_ref": exact("EvalReportRevision", "eval-safety"),
        "copyright_eval_ref": exact("EvalReportRevision", "eval-copyright"),
        "avatar_capability_ref": exact("CapabilityRevision", "avatar-stream"),
        "avatar_binding_ref": mutable("CapabilityBinding", "avatar-binding"),
        "tts_capability_ref": exact("CapabilityRevision", "tts-stream"),
        "tts_binding_ref": mutable("CapabilityBinding", "tts-binding"),
        "budget_ref": exact("BudgetRevision", "budget-1"),
        "kill_policy_ref": exact("KillPolicyRevision", "kill-policy-1"),
        "human_operator_ref": mutable("HumanOperatorAssignment", "operator-1"),
        "agent_stages": stages(),
        "latency_budget": LiveLatencyBudget(
            understanding_ms=250,
            retrieval_ms=350,
            drafting_ms=850,
            safety_ms=300,
            director_ms=150,
            tts_first_packet_ms=450,
            avatar_first_frame_ms=500,
            total_target_ms=2900,
        ),
    }
    values.update(overrides)
    return LiveSandboxManifest(**values)


def observation(**overrides: object) -> LiveReadinessObservation:
    values: dict[str, object] = {
        "provider_instance_ref": exact("ProviderInstanceRevision", "agnes-live"),
        "model_route_ref": exact("ModelRouteRevision", "live-route"),
        "runtime_policy_ref": exact("RuntimePolicyRevision", "live-policy"),
        "provider_health_refs": [
            exact("ProviderHealthObservation", f"health-{index}") for index in range(1, 4)
        ],
        "capacity_ref": exact("CapacitySnapshot", "capacity-1"),
        "price_ref": exact("PriceSnapshot", "price-1"),
        "budget_balance_ref": exact("BudgetBalanceSnapshot", "balance-1"),
        "profile_license_ref": exact("AssetLicenseRevision", "profile-license-1"),
        "voice_license_ref": exact("AssetLicenseRevision", "voice-license-1"),
        "planned_start_at": NOW + timedelta(minutes=5),
        "health_valid_from": NOW - timedelta(minutes=1),
        "health_expires_at": NOW + timedelta(minutes=10),
        "capacity_ready": True,
        "price_ready": True,
        "budget_balance_ready": True,
        "profile_license_ready": True,
        "voice_license_ready": True,
        "tts_streaming_ready": True,
        "avatar_streaming_ready": True,
        "internal_stream_ready": True,
        "knowledge_snapshot_fresh": True,
        "evals_passed": True,
        "human_heartbeat_ready": True,
        "kill_switch_ready": True,
        "r21_fact_content_chain_ready": True,
        "observed_at": NOW,
    }
    values.update(overrides)
    return LiveReadinessObservation(**values)


def signal(**overrides: object) -> LiveInteractionSignal:
    values: dict[str, object] = {
        "interaction_id": "interaction-1",
        "sanitized_text_hash": HASH,
        "pii_detected": False,
        "injection_detected": False,
        "hard_gates": [],
        "knowledge_state": KnowledgeState.FRESH,
        "knowledge_match_ref": artifact("live_knowledge_match", "match-1"),
        "script_draft_ref": artifact("live_script_draft", "draft-1"),
        "safety_passed": True,
        "human_operator_available": True,
        "active_segment": False,
        "session_live": True,
    }
    values.update(overrides)
    return LiveInteractionSignal(**values)


def test_manifest_freezes_internal_300_second_five_agent_pipeline() -> None:
    value = manifest()
    assert value.mode == "internal_sandbox"
    assert value.duration_seconds == 300
    assert [stage.role for stage in value.agent_stages] == list(LiveAgentRole)


def test_manifest_rejects_non_five_minute_or_platform_mode() -> None:
    with pytest.raises(ValidationError, match="durationSeconds"):
        manifest(duration_seconds=299)
    with pytest.raises(ValidationError):
        manifest(mode="douyin_rtmp")


def test_manifest_rejects_reordered_or_non_exact_chain() -> None:
    bad = stages()
    bad[0], bad[1] = bad[1], bad[0]
    with pytest.raises(ValidationError, match="five Agent stages"):
        manifest(agent_stages=bad)
    with pytest.raises(ValidationError, match="livePlanRef"):
        manifest(live_plan_ref=ArtifactRef(artifact_id="plan", artifact_type="live_plan"))


def test_latency_budget_must_remain_below_three_seconds() -> None:
    with pytest.raises(ValidationError, match="below 3000ms"):
        LiveLatencyBudget(
            understanding_ms=400,
            retrieval_ms=400,
            drafting_ms=900,
            safety_ms=300,
            director_ms=200,
            tts_first_packet_ms=400,
            avatar_first_frame_ms=400,
            total_target_ms=3000,
        )


def test_health_requires_three_distinct_start_time_observations() -> None:
    with pytest.raises(ValidationError, match="exactly three distinct"):
        observation(provider_health_refs=[exact("ProviderHealthObservation", "health-1")])


def test_ready_observation_produces_ready_code_control_decision() -> None:
    decision = assess_live_sandbox_readiness(manifest(), observation())
    assert decision.readiness == "ready"
    assert decision.blockers == []
    assert decision.execution_authorized is False


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"health_expires_at": NOW + timedelta(minutes=1)}, "LIVE_PROVIDER_HEALTH_NOT_3_OF_3_FRESH"),
        ({"knowledge_snapshot_fresh": False}, "LIVE_KNOWLEDGE_SNAPSHOT_STALE"),
        ({"budget_balance_ready": False}, "LIVE_BUDGET_BALANCE_UNAVAILABLE"),
        ({"human_heartbeat_ready": False}, "LIVE_HUMAN_HEARTBEAT_UNAVAILABLE"),
        ({"r21_fact_content_chain_ready": False}, "LIVE_R21_FACT_CONTENT_CHAIN_UNAVAILABLE"),
    ],
)
def test_readiness_fails_closed_for_each_missing_runtime_gate(
    changes: dict[str, object], code: str
) -> None:
    decision = assess_live_sandbox_readiness(manifest(), observation(**changes))
    assert decision.readiness == "blocked"
    assert code in {blocker.code for blocker in decision.blockers}
    assert decision.execution_authorized is False


def test_safe_interaction_only_becomes_ready_for_human_release() -> None:
    decision = decide_live_interaction(signal())
    assert decision.action is DirectorAction.READY_FOR_OPERATOR_RELEASE
    assert decision.requires_human_release is True
    assert decision.kill_level is None


def test_active_segment_queues_instead_of_interrupting() -> None:
    decision = decide_live_interaction(signal(active_segment=True))
    assert decision.action is DirectorAction.QUEUE
    assert decision.requires_human_release is True


@pytest.mark.parametrize("risk_field", ["pii_detected", "injection_detected"])
def test_untrusted_danmu_risk_requires_human_takeover(risk_field: str) -> None:
    decision = decide_live_interaction(signal(**{risk_field: True}))
    assert decision.action is DirectorAction.HUMAN_TAKEOVER
    assert decision.kill_level is KillLevel.PAUSE


def test_hard_gate_without_human_escalates_to_session_kill() -> None:
    decision = decide_live_interaction(
        signal(hard_gates=["medical_claim"], human_operator_available=False)
    )
    assert decision.action is DirectorAction.KILL_SESSION
    assert decision.kill_level is KillLevel.KILL_SESSION


def test_stale_or_missing_knowledge_never_reaches_script_release() -> None:
    stale = signal(
        knowledge_state=KnowledgeState.STALE,
        knowledge_match_ref=None,
        script_draft_ref=None,
        safety_passed=False,
    )
    decision = decide_live_interaction(stale)
    assert decision.action is DirectorAction.HUMAN_TAKEOVER
    assert decision.reason_code == "LIVE_KNOWLEDGE_NOT_FRESH"


def test_stale_knowledge_without_human_kills_instead_of_fake_handoff() -> None:
    decision = decide_live_interaction(
        signal(
            knowledge_state=KnowledgeState.MISSING,
            knowledge_match_ref=None,
            script_draft_ref=None,
            safety_passed=False,
            human_operator_available=False,
        )
    )
    assert decision.action is DirectorAction.KILL_SESSION
    assert decision.reason_code == "LIVE_KNOWLEDGE_UNAVAILABLE_WITHOUT_HUMAN"


def test_kill_ladder_escalates_deterministically_and_never_wraps() -> None:
    assert escalate_kill_level(KillLevel.MUTE) is KillLevel.PAUSE
    assert escalate_kill_level(KillLevel.PAUSE) is KillLevel.KILL_SESSION
    assert escalate_kill_level(KillLevel.KILL_SESSION) is KillLevel.ISOLATE_PROVIDER
    assert escalate_kill_level(KillLevel.ISOLATE_PROVIDER) is KillLevel.ISOLATE_PROVIDER
