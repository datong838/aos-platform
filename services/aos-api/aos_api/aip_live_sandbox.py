"""Fail-closed planning contracts for the R23 digital-human live sandbox.

This module is deliberately side-effect free.  It neither opens an
``AvatarSession`` nor calls an LLM, TTS, avatar, barrage, or streaming engine.
It composes exact authority observations into a readiness decision and turns
metadata-only interaction signals into operator-gated director decisions.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, ArtifactRef
from aos_api.aip_production_contracts import (
    ContractBlocker,
    ContractReadiness,
    ExactRevisionRef,
    MutableAuthorityRef,
)


class LiveAgentRole(StrEnum):
    DANMU_UNDERSTANDING = "danmu_understanding"
    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"
    SCRIPT_DRAFTING = "script_drafting"
    SAFETY_FILTERING = "safety_filtering"
    DIRECTOR_CONTROL = "director_control"


class KnowledgeState(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    MISSING = "missing"
    UNKNOWN = "unknown"


class DirectorAction(StrEnum):
    READY_FOR_OPERATOR_RELEASE = "ready_for_operator_release"
    QUEUE = "queue"
    SILENT = "silent"
    HUMAN_TAKEOVER = "human_takeover"
    KILL_SESSION = "kill_session"


class KillLevel(StrEnum):
    MUTE = "mute"
    PAUSE = "pause"
    KILL_SESSION = "kill_session"
    ISOLATE_PROVIDER = "isolate_provider"


HARD_GATES = frozenset(
    {
        "medical_claim",
        "financial_claim",
        "legal_claim",
        "minor_safety",
        "personal_information",
        "abuse_conflict",
        "price_conflict",
        "inventory_conflict",
        "platform_rule_unknown",
        "model_unavailable",
        "knowledge_unavailable",
    }
)

_STAGE_CHAIN: tuple[tuple[LiveAgentRole, str, str], ...] = (
    (
        LiveAgentRole.DANMU_UNDERSTANDING,
        "SanitizedDanmuEnvelope",
        "DanmuUnderstandingArtifact",
    ),
    (
        LiveAgentRole.KNOWLEDGE_RETRIEVAL,
        "DanmuUnderstandingArtifact",
        "LiveKnowledgeMatchArtifact",
    ),
    (
        LiveAgentRole.SCRIPT_DRAFTING,
        "LiveKnowledgeMatchArtifact",
        "LiveScriptDraftArtifact",
    ),
    (
        LiveAgentRole.SAFETY_FILTERING,
        "LiveScriptDraftArtifact",
        "LiveSafetyDecisionArtifact",
    ),
    (
        LiveAgentRole.DIRECTOR_CONTROL,
        "LiveSafetyDecisionArtifact",
        "LiveDirectorDecisionArtifact",
    ),
)


def _require_exact_artifact(value: ArtifactRef, expected_type: str, label: str) -> None:
    if value.artifact_type != expected_type:
        raise ValueError(f"{label} must reference {expected_type}")
    if not value.revision or not value.content_hash:
        raise ValueError(f"{label} requires exact revision and contentHash")


def _require_exact_type(value: ExactRevisionRef, expected_type: str, label: str) -> None:
    if value.resource_type != expected_type:
        raise ValueError(f"{label} must reference {expected_type}")


def _require_mutable_type(value: MutableAuthorityRef, expected_type: str, label: str) -> None:
    if value.resource_type != expected_type:
        raise ValueError(f"{label} must reference {expected_type}")


class LiveAgentStage(AipContractModel):
    order: int = Field(ge=1, le=5)
    role: LiveAgentRole
    capability_ref: ExactRevisionRef
    input_artifact_type: str = Field(min_length=1, max_length=120)
    output_artifact_type: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def _exact_capability(self) -> "LiveAgentStage":
        _require_exact_type(self.capability_ref, "CapabilityRevision", "capabilityRef")
        return self


class LiveLatencyBudget(AipContractModel):
    understanding_ms: int = Field(ge=1, le=2_999)
    retrieval_ms: int = Field(ge=1, le=2_999)
    drafting_ms: int = Field(ge=1, le=2_999)
    safety_ms: int = Field(ge=1, le=2_999)
    director_ms: int = Field(ge=1, le=2_999)
    tts_first_packet_ms: int = Field(ge=1, le=2_999)
    avatar_first_frame_ms: int = Field(ge=1, le=2_999)
    total_target_ms: int = Field(ge=1, le=3_000)

    @model_validator(mode="after")
    def _below_three_seconds(self) -> "LiveLatencyBudget":
        components = (
            self.understanding_ms,
            self.retrieval_ms,
            self.drafting_ms,
            self.safety_ms,
            self.director_ms,
            self.tts_first_packet_ms,
            self.avatar_first_frame_ms,
        )
        if self.total_target_ms >= 3_000 or sum(components) > self.total_target_ms:
            raise ValueError("live latency budget must remain below 3000ms")
        return self


class LiveSandboxManifest(AipContractModel):
    mode: Literal["internal_sandbox"] = "internal_sandbox"
    duration_seconds: int = Field(ge=1, le=21_600)
    live_plan_ref: ArtifactRef
    knowledge_snapshot_ref: ArtifactRef
    digital_human_profile_ref: ExactRevisionRef
    factuality_eval_ref: ExactRevisionRef
    safety_eval_ref: ExactRevisionRef
    copyright_eval_ref: ExactRevisionRef
    avatar_capability_ref: ExactRevisionRef
    avatar_binding_ref: MutableAuthorityRef
    tts_capability_ref: ExactRevisionRef
    tts_binding_ref: MutableAuthorityRef
    budget_ref: ExactRevisionRef
    kill_policy_ref: ExactRevisionRef
    human_operator_ref: MutableAuthorityRef
    agent_stages: list[LiveAgentStage] = Field(min_length=5, max_length=5)
    latency_budget: LiveLatencyBudget

    @model_validator(mode="after")
    def _strict_live_composition(self) -> "LiveSandboxManifest":
        if self.duration_seconds != 300:
            raise ValueError("durationSeconds must be exactly 300 for the R23 sandbox")
        _require_exact_artifact(self.live_plan_ref, "live_plan", "livePlanRef")
        _require_exact_artifact(
            self.knowledge_snapshot_ref,
            "live_knowledge_snapshot",
            "knowledgeSnapshotRef",
        )
        for value, expected, label in (
            (self.digital_human_profile_ref, "DigitalHumanProfileRevision", "digitalHumanProfileRef"),
            (self.factuality_eval_ref, "EvalReportRevision", "factualityEvalRef"),
            (self.safety_eval_ref, "EvalReportRevision", "safetyEvalRef"),
            (self.copyright_eval_ref, "EvalReportRevision", "copyrightEvalRef"),
            (self.avatar_capability_ref, "CapabilityRevision", "avatarCapabilityRef"),
            (self.tts_capability_ref, "CapabilityRevision", "ttsCapabilityRef"),
            (self.budget_ref, "BudgetRevision", "budgetRef"),
            (self.kill_policy_ref, "KillPolicyRevision", "killPolicyRef"),
        ):
            _require_exact_type(value, expected, label)
        _require_mutable_type(self.avatar_binding_ref, "CapabilityBinding", "avatarBindingRef")
        _require_mutable_type(self.tts_binding_ref, "CapabilityBinding", "ttsBindingRef")
        _require_mutable_type(
            self.human_operator_ref,
            "HumanOperatorAssignment",
            "humanOperatorRef",
        )
        actual = [
            (stage.role, stage.input_artifact_type, stage.output_artifact_type)
            for stage in self.agent_stages
        ]
        expected = [(role, input_type, output_type) for role, input_type, output_type in _STAGE_CHAIN]
        if actual != expected or [stage.order for stage in self.agent_stages] != [1, 2, 3, 4, 5]:
            raise ValueError("five Agent stages must use the canonical order and artifact chain")
        capability_ids = [stage.capability_ref.resource_id for stage in self.agent_stages]
        if len(capability_ids) != len(set(capability_ids)):
            raise ValueError("five Agent capabilities must be distinct")
        return self


class LiveReadinessObservation(AipContractModel):
    provider_instance_ref: ExactRevisionRef
    model_route_ref: ExactRevisionRef
    runtime_policy_ref: ExactRevisionRef
    provider_health_refs: list[ExactRevisionRef] = Field(min_length=1, max_length=3)
    capacity_ref: ExactRevisionRef
    price_ref: ExactRevisionRef
    budget_balance_ref: ExactRevisionRef
    profile_license_ref: ExactRevisionRef
    voice_license_ref: ExactRevisionRef
    planned_start_at: datetime
    health_valid_from: datetime
    health_expires_at: datetime
    capacity_ready: bool
    price_ready: bool
    budget_balance_ready: bool
    profile_license_ready: bool
    voice_license_ready: bool
    tts_streaming_ready: bool
    avatar_streaming_ready: bool
    internal_stream_ready: bool
    knowledge_snapshot_fresh: bool
    evals_passed: bool
    human_heartbeat_ready: bool
    kill_switch_ready: bool
    r21_fact_content_chain_ready: bool
    observed_at: datetime

    @model_validator(mode="after")
    def _exact_runtime_observations(self) -> "LiveReadinessObservation":
        for value, expected, label in (
            (self.provider_instance_ref, "ProviderInstanceRevision", "providerInstanceRef"),
            (self.model_route_ref, "ModelRouteRevision", "modelRouteRef"),
            (self.runtime_policy_ref, "RuntimePolicyRevision", "runtimePolicyRef"),
            (self.capacity_ref, "CapacitySnapshot", "capacityRef"),
            (self.price_ref, "PriceSnapshot", "priceRef"),
            (self.budget_balance_ref, "BudgetBalanceSnapshot", "budgetBalanceRef"),
            (self.profile_license_ref, "AssetLicenseRevision", "profileLicenseRef"),
            (self.voice_license_ref, "AssetLicenseRevision", "voiceLicenseRef"),
        ):
            _require_exact_type(value, expected, label)
        health_ids: list[str] = []
        for value in self.provider_health_refs:
            _require_exact_type(value, "ProviderHealthObservation", "providerHealthRefs")
            health_ids.append(value.resource_id)
        if len(health_ids) != 3 or len(set(health_ids)) != 3:
            raise ValueError("providerHealthRefs requires exactly three distinct observations")
        for label, value in (
            ("observedAt", self.observed_at),
            ("plannedStartAt", self.planned_start_at),
            ("healthValidFrom", self.health_valid_from),
            ("healthExpiresAt", self.health_expires_at),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{label} must be timezone-aware")
        if not self.health_valid_from < self.health_expires_at:
            raise ValueError("health validity window must be increasing")
        return self

    @property
    def health_fresh(self) -> bool:
        return (
            self.health_valid_from
            <= self.observed_at
            <= self.planned_start_at
            < self.health_expires_at
        )


class LiveReadinessDecision(AipContractModel):
    readiness: ContractReadiness
    blockers: list[ContractBlocker]
    execution_authorized: Literal[False] = False


_READINESS_GATES: tuple[tuple[str, str, str], ...] = (
    ("health_fresh", "LIVE_PROVIDER_HEALTH_NOT_3_OF_3_FRESH", "Provider Health is not fresh 3/3"),
    ("capacity_ready", "LIVE_CAPACITY_UNAVAILABLE", "Avatar/TTS capacity is unavailable"),
    ("price_ready", "LIVE_PRICE_UNAVAILABLE", "Exact live price snapshot is unavailable"),
    ("budget_balance_ready", "LIVE_BUDGET_BALANCE_UNAVAILABLE", "Budget balance authority is unavailable"),
    ("profile_license_ready", "LIVE_PROFILE_LICENSE_UNAVAILABLE", "Digital-human profile license is unavailable"),
    ("voice_license_ready", "LIVE_VOICE_LICENSE_UNAVAILABLE", "Voice license is unavailable"),
    ("tts_streaming_ready", "LIVE_TTS_STREAMING_UNAVAILABLE", "Streaming TTS is unavailable"),
    ("avatar_streaming_ready", "LIVE_AVATAR_STREAMING_UNAVAILABLE", "Avatar streaming is unavailable"),
    ("internal_stream_ready", "LIVE_INTERNAL_STREAM_UNAVAILABLE", "Internal sandbox stream is unavailable"),
    ("knowledge_snapshot_fresh", "LIVE_KNOWLEDGE_SNAPSHOT_STALE", "Live knowledge snapshot is not fresh"),
    ("evals_passed", "LIVE_EVALS_NOT_PASSED", "Factuality, safety, and copyright Evals have not passed"),
    ("human_heartbeat_ready", "LIVE_HUMAN_HEARTBEAT_UNAVAILABLE", "Human operator heartbeat is unavailable"),
    ("kill_switch_ready", "LIVE_KILL_SWITCH_UNAVAILABLE", "Four-level kill switch is unavailable"),
    ("r21_fact_content_chain_ready", "LIVE_R21_FACT_CONTENT_CHAIN_UNAVAILABLE", "R21 product fact and content chain is unavailable"),
)


def assess_live_sandbox_readiness(
    manifest: LiveSandboxManifest,
    observation: LiveReadinessObservation,
) -> LiveReadinessDecision:
    """Compose exact observations without authorizing execution."""

    del manifest  # Validation of the strict manifest is the only use here.
    blockers = [
        ContractBlocker(code=code, message=message)
        for attribute, code, message in _READINESS_GATES
        if not getattr(observation, attribute)
    ]
    return LiveReadinessDecision(
        readiness=ContractReadiness.BLOCKED if blockers else ContractReadiness.READY,
        blockers=blockers,
    )


class LiveInteractionSignal(AipContractModel):
    interaction_id: str = Field(min_length=1, max_length=200)
    sanitized_text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    pii_detected: bool
    injection_detected: bool
    hard_gates: list[str] = Field(default_factory=list, max_length=20)
    knowledge_state: KnowledgeState
    knowledge_match_ref: ArtifactRef | None = None
    script_draft_ref: ArtifactRef | None = None
    safety_passed: bool
    human_operator_available: bool
    active_segment: bool
    session_live: bool

    @model_validator(mode="after")
    def _metadata_only_chain(self) -> "LiveInteractionSignal":
        unknown = set(self.hard_gates) - HARD_GATES
        if unknown:
            raise ValueError(f"unknown hard gates: {sorted(unknown)}")
        if self.knowledge_match_ref:
            _require_exact_artifact(
                self.knowledge_match_ref,
                "live_knowledge_match",
                "knowledgeMatchRef",
            )
        if self.script_draft_ref:
            _require_exact_artifact(
                self.script_draft_ref,
                "live_script_draft",
                "scriptDraftRef",
            )
        if self.knowledge_state is KnowledgeState.FRESH and not self.knowledge_match_ref:
            raise ValueError("fresh knowledge requires knowledgeMatchRef")
        if self.safety_passed and not self.script_draft_ref:
            raise ValueError("passed safety requires scriptDraftRef")
        return self


class LiveDirectorDecision(AipContractModel):
    action: DirectorAction
    reason_code: str = Field(min_length=1, max_length=160)
    requires_human_release: bool
    kill_level: KillLevel | None = None

    @model_validator(mode="after")
    def _operator_and_kill_integrity(self) -> "LiveDirectorDecision":
        if self.action in {DirectorAction.HUMAN_TAKEOVER, DirectorAction.KILL_SESSION}:
            if self.kill_level is None:
                raise ValueError("human takeover or kill requires killLevel")
        elif self.kill_level is not None:
            raise ValueError("non-escalation decision cannot carry killLevel")
        if self.action is DirectorAction.READY_FOR_OPERATOR_RELEASE and not self.requires_human_release:
            raise ValueError("ready interaction still requires explicit human release")
        return self


def decide_live_interaction(signal: LiveInteractionSignal) -> LiveDirectorDecision:
    """Return a metadata-only, operator-gated director decision."""

    risk = signal.pii_detected or signal.injection_detected or bool(signal.hard_gates)
    if risk:
        if signal.human_operator_available:
            return LiveDirectorDecision(
                action=DirectorAction.HUMAN_TAKEOVER,
                reason_code="LIVE_UNTRUSTED_INPUT_OR_HARD_GATE",
                requires_human_release=True,
                kill_level=KillLevel.PAUSE,
            )
        return LiveDirectorDecision(
            action=DirectorAction.KILL_SESSION,
            reason_code="LIVE_HARD_GATE_WITHOUT_HUMAN_OPERATOR",
            requires_human_release=False,
            kill_level=KillLevel.KILL_SESSION,
        )
    if signal.knowledge_state is not KnowledgeState.FRESH:
        if not signal.human_operator_available:
            return LiveDirectorDecision(
                action=DirectorAction.KILL_SESSION,
                reason_code="LIVE_KNOWLEDGE_UNAVAILABLE_WITHOUT_HUMAN",
                requires_human_release=False,
                kill_level=KillLevel.KILL_SESSION,
            )
        return LiveDirectorDecision(
            action=DirectorAction.HUMAN_TAKEOVER,
            reason_code="LIVE_KNOWLEDGE_NOT_FRESH",
            requires_human_release=True,
            kill_level=KillLevel.PAUSE,
        )
    if not signal.session_live:
        return LiveDirectorDecision(
            action=DirectorAction.QUEUE,
            reason_code="LIVE_SESSION_NOT_LIVE",
            requires_human_release=True,
        )
    if not signal.safety_passed or not signal.script_draft_ref:
        return LiveDirectorDecision(
            action=DirectorAction.SILENT,
            reason_code="LIVE_SCRIPT_NOT_SAFETY_APPROVED",
            requires_human_release=True,
        )
    if signal.active_segment:
        return LiveDirectorDecision(
            action=DirectorAction.QUEUE,
            reason_code="LIVE_ACTIVE_SEGMENT_PROTECTED",
            requires_human_release=True,
        )
    return LiveDirectorDecision(
        action=DirectorAction.READY_FOR_OPERATOR_RELEASE,
        reason_code="LIVE_LOW_RISK_DRAFT_READY_FOR_OPERATOR_RELEASE",
        requires_human_release=True,
    )


_KILL_LADDER = {
    KillLevel.MUTE: KillLevel.PAUSE,
    KillLevel.PAUSE: KillLevel.KILL_SESSION,
    KillLevel.KILL_SESSION: KillLevel.ISOLATE_PROVIDER,
    KillLevel.ISOLATE_PROVIDER: KillLevel.ISOLATE_PROVIDER,
}


def escalate_kill_level(current: KillLevel) -> KillLevel:
    """Escalate monotonically; isolation is terminal and never wraps."""

    return _KILL_LADDER[current]


__all__ = [
    "DirectorAction",
    "HARD_GATES",
    "KillLevel",
    "KnowledgeState",
    "LiveAgentRole",
    "LiveAgentStage",
    "LiveDirectorDecision",
    "LiveInteractionSignal",
    "LiveLatencyBudget",
    "LiveReadinessDecision",
    "LiveReadinessObservation",
    "LiveSandboxManifest",
    "assess_live_sandbox_readiness",
    "decide_live_interaction",
    "escalate_kill_level",
]
