"""Strict GET-only W8-06 batch prepare/start/reconcile scenario contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel


BATCH_SCENARIO_SCHEMA_VERSION = "aos.ecommerce-workshop.batch-scenario/v1"


class BatchScenarioStageId(StrEnum):
    PREPARE_ROOT = "prepare_root"
    IMPACT_COST_PREVIEW = "impact_cost_preview"
    EXPLICIT_START = "explicit_start"
    CHILD_DISPATCH = "child_dispatch"
    PARTIAL_OUTCOMES = "partial_outcomes"
    UNKNOWN_RECONCILE = "unknown_reconcile"
    RESTART_REBUILD = "restart_rebuild"


class BatchScenarioOutcomeAxisId(StrEnum):
    BUSINESS_ITEM = "business_item"
    EXTERNAL_ACTION = "external_action"
    USAGE_SETTLEMENT = "usage_settlement"
    EFFECT_MATURITY = "effect_maturity"
    HANDOFF_DECISION = "handoff_decision"


class BatchScenarioExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class BatchScenarioBlocker(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    dependency: str = Field(min_length=1, max_length=180)
    required_action: str = Field(min_length=1, max_length=500)


class BatchScenarioRoleBinding(AipContractModel):
    role_ref: BatchScenarioExactRef
    assignee_ref: BatchScenarioExactRef
    skill_binding_ref: BatchScenarioExactRef

    @model_validator(mode="after")
    def _layer_types_are_exact(self) -> "BatchScenarioRoleBinding":
        if self.role_ref.resource_type != "AgentTemplate":
            raise ValueError("batch scenario role must be AgentTemplate")
        if self.assignee_ref.resource_type != "AgentInstance":
            raise ValueError("batch scenario assignee must be AgentInstance")
        if self.skill_binding_ref.resource_type != "SkillBinding":
            raise ValueError("batch scenario binding must be SkillBinding")
        return self


class BatchScenarioComposition(AipContractModel):
    atomic_skill_refs: list[BatchScenarioExactRef] = Field(min_length=1, max_length=30)
    logic_revision_ref: BatchScenarioExactRef
    role_bindings: list[BatchScenarioRoleBinding] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def _four_layers_are_exact(self) -> "BatchScenarioComposition":
        if any(ref.resource_type != "SkillRevision" for ref in self.atomic_skill_refs):
            raise ValueError("batch scenario atomic skills must be SkillRevision")
        if self.logic_revision_ref.resource_type != "LogicRevision":
            raise ValueError("batch scenario logic must be LogicRevision")
        skills = [(ref.resource_id, ref.revision, ref.content_hash) for ref in self.atomic_skill_refs]
        bindings = [item.skill_binding_ref.resource_id for item in self.role_bindings]
        if len(skills) != len(set(skills)) or len(bindings) != len(set(bindings)):
            raise ValueError("batch scenario composition identities must be unique")
        return self


class BatchScenarioPreparationDecision(AipContractModel):
    item_key: str = Field(min_length=1, max_length=200)
    disposition: Literal["included", "excluded", "blocked", "unknown"]
    original_refs: list[BatchScenarioExactRef] = Field(min_length=1, max_length=20)
    decision_ref: BatchScenarioExactRef
    reason_codes: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _honest_decision(self) -> "BatchScenarioPreparationDecision":
        if self.decision_ref.resource_type != "ItemPreparationDecision":
            raise ValueError("batch preparation decision must use ItemPreparationDecision")
        identities = [(ref.resource_type, ref.resource_id, ref.revision, ref.content_hash) for ref in self.original_refs]
        if len(identities) != len(set(identities)):
            raise ValueError("batch preparation original refs must be unique")
        if self.disposition in {"blocked", "unknown"} and not self.reason_codes:
            raise ValueError("blocked or unknown preparation requires reason codes")
        return self


class BatchScenarioChildOutcome(AipContractModel):
    item_key: str = Field(min_length=1, max_length=200)
    status: Literal["succeeded", "failed", "cancelled", "unknown", "reconciled"]
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    attempt_ref: BatchScenarioExactRef
    authority_refs: list[BatchScenarioExactRef] = Field(min_length=1, max_length=20)
    reconcile_receipt_refs: list[BatchScenarioExactRef] = Field(default_factory=list, max_length=20)
    automatic_retry_allowed: Literal[False] = False

    @model_validator(mode="after")
    def _honest_outcome(self) -> "BatchScenarioChildOutcome":
        if self.attempt_ref.resource_type != "Attempt":
            raise ValueError("batch child outcome must use an exact Attempt")
        if self.status == "unknown" and self.reconcile_receipt_refs:
            raise ValueError("unknown batch outcome cannot claim reconcile receipts")
        if self.status == "reconciled" and not self.reconcile_receipt_refs:
            raise ValueError("reconciled batch outcome requires reconcile receipts")
        return self


class BatchScenarioStage(AipContractModel):
    stage_id: BatchScenarioStageId
    status: Literal["ready", "blocked", "unknown"]
    exact_refs: list[BatchScenarioExactRef] = Field(default_factory=list, max_length=50)
    contribution: str = Field(min_length=1, max_length=500)
    blockers: list[BatchScenarioBlocker] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _honest_stage(self) -> "BatchScenarioStage":
        identities = [(ref.resource_type, ref.resource_id, ref.revision, ref.content_hash) for ref in self.exact_refs]
        if len(identities) != len(set(identities)):
            raise ValueError("batch scenario stage exact refs must be unique")
        if self.status == "ready" and (not self.exact_refs or self.blockers):
            raise ValueError("ready batch stage requires exact refs and no blockers")
        if self.status != "ready" and (self.exact_refs or not self.blockers):
            raise ValueError("non-ready batch stage requires blockers and no trusted refs")
        return self


class BatchScenarioLedger(AipContractModel):
    frozen_total: int = Field(ge=0)
    included: int = Field(ge=0)
    excluded: int = Field(ge=0)
    blocked: int = Field(ge=0)
    preparation_unknown: int = Field(ge=0)
    children_expected: int = Field(ge=0)
    children_observed: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    cancelled: int = Field(ge=0)
    child_unknown: int = Field(ge=0)
    reconciled: int = Field(ge=0)
    reconcile_receipts_observed: int = Field(ge=0)

    @model_validator(mode="after")
    def _conserves(self) -> "BatchScenarioLedger":
        if self.frozen_total != self.included + self.excluded + self.blocked + self.preparation_unknown:
            raise ValueError("batch preparation ledger must conserve frozen total")
        if self.children_expected != self.included or self.children_observed > self.children_expected:
            raise ValueError("batch child counts must follow included preparation decisions")
        if self.children_observed != self.succeeded + self.failed + self.cancelled + self.child_unknown + self.reconciled:
            raise ValueError("batch outcome ledger must conserve observed children")
        if self.reconcile_receipts_observed < self.reconciled:
            raise ValueError("reconciled children require observed reconcile receipts")
        return self


class BatchScenarioOutcomeAxis(AipContractModel):
    axis_id: BatchScenarioOutcomeAxisId
    status: Literal["succeeded", "partial", "failed", "cancelled", "blocked", "unknown", "reconciled", "not_started"]
    exact_refs: list[BatchScenarioExactRef] = Field(default_factory=list, max_length=30)
    blockers: list[BatchScenarioBlocker] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _honest_axis(self) -> "BatchScenarioOutcomeAxis":
        if self.status in {"succeeded", "reconciled"} and (not self.exact_refs or self.blockers):
            raise ValueError("settled batch outcome axis requires exact refs and no blockers")
        if self.status == "partial" and (not self.exact_refs or not self.blockers):
            raise ValueError("partial batch outcome axis requires exact refs and blockers")
        if self.status not in {"succeeded", "reconciled", "partial"} and (self.exact_refs or not self.blockers):
            raise ValueError("unsettled batch outcome axis requires blockers and no trusted refs")
        return self


class BatchScenarioSideEffectLedger(AipContractModel):
    prepare_external_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    action_attempts: Literal[0] = 0
    external_effects: Literal[0] = 0


class BatchScenarioCommands(AipContractModel):
    prepare: Literal[False] = False
    start: Literal[False] = False
    cancel: Literal[False] = False
    reconcile: Literal[False] = False


class BatchScenarioContribution(AipContractModel):
    schema_version: Literal[BATCH_SCENARIO_SCHEMA_VERSION] = BATCH_SCENARIO_SCHEMA_VERSION
    status: Literal["blocked"] = "blocked"
    batch_preparation_revision_ref: BatchScenarioExactRef | None = None
    batch_start_decision_ref: BatchScenarioExactRef | None = None
    batch_start_binding_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    composition: BatchScenarioComposition | None = None
    evaluated_at: datetime
    preparation_decisions: list[BatchScenarioPreparationDecision] = Field(default_factory=list, max_length=500)
    child_outcomes: list[BatchScenarioChildOutcome] = Field(default_factory=list, max_length=500)
    stages: list[BatchScenarioStage] = Field(min_length=7, max_length=7)
    ledger: BatchScenarioLedger
    outcome_axes: list[BatchScenarioOutcomeAxis] = Field(min_length=5, max_length=5)
    side_effect_ledger: BatchScenarioSideEffectLedger = Field(default_factory=BatchScenarioSideEffectLedger)
    blockers: list[BatchScenarioBlocker] = Field(min_length=1, max_length=80)
    commands: BatchScenarioCommands = Field(default_factory=BatchScenarioCommands)
    automatic_retry_allowed: Literal[False] = False
    external_effects_allowed: Literal[False] = False
    release_allowed: Literal[False] = False

    @field_validator("evaluated_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("batch scenario evaluation requires timezone")
        return value

    @model_validator(mode="after")
    def _canonical_and_fail_closed(self) -> "BatchScenarioContribution":
        if [stage.stage_id for stage in self.stages] != list(BatchScenarioStageId):
            raise ValueError("batch scenario stages require canonical order")
        if [axis.axis_id for axis in self.outcome_axes] != list(BatchScenarioOutcomeAxisId):
            raise ValueError("batch scenario outcome axes require canonical order")
        roots = (self.batch_preparation_revision_ref, self.batch_start_decision_ref, self.batch_start_binding_hash, self.composition)
        if any(item is None for item in roots) != all(item is None for item in roots):
            raise ValueError("batch roots, binding and composition must appear together")
        if self.batch_preparation_revision_ref is not None and self.batch_preparation_revision_ref.resource_type != "BatchPreparationRevision":
            raise ValueError("batch preparation root must be BatchPreparationRevision")
        if self.batch_start_decision_ref is not None and self.batch_start_decision_ref.resource_type != "BatchStartDecision":
            raise ValueError("batch start root must be BatchStartDecision")
        keys = [item.item_key for item in self.preparation_decisions]
        child_keys = [item.item_key for item in self.child_outcomes]
        if len(keys) != len(set(keys)) or len(child_keys) != len(set(child_keys)):
            raise ValueError("batch scenario item keys must be unique")
        included = {item.item_key for item in self.preparation_decisions if item.disposition == "included"}
        if not set(child_keys).issubset(included):
            raise ValueError("batch child outcomes must belong to included items")
        dispositions = {name: sum(item.disposition == name for item in self.preparation_decisions) for name in ("included", "excluded", "blocked", "unknown")}
        if self.preparation_decisions and (self.ledger.included, self.ledger.excluded, self.ledger.blocked, self.ledger.preparation_unknown) != (dispositions["included"], dispositions["excluded"], dispositions["blocked"], dispositions["unknown"]):
            raise ValueError("batch preparation decisions must match ledger")
        statuses = {name: sum(item.status == name for item in self.child_outcomes) for name in ("succeeded", "failed", "cancelled", "unknown", "reconciled")}
        if self.child_outcomes and (self.ledger.succeeded, self.ledger.failed, self.ledger.cancelled, self.ledger.child_unknown, self.ledger.reconciled) != (statuses["succeeded"], statuses["failed"], statuses["cancelled"], statuses["unknown"], statuses["reconciled"]):
            raise ValueError("batch child outcomes must match ledger")
        root_stage = self.stages[0]
        if self.batch_preparation_revision_ref is not None and root_stage.status == "ready" and (self.batch_preparation_revision_ref not in root_stage.exact_refs or self.batch_start_decision_ref not in root_stage.exact_refs):
            raise ValueError("batch roots must be included in prepare_root stage")
        if not any(stage.status != "ready" for stage in self.stages) and not any(axis.status not in {"succeeded", "reconciled"} for axis in self.outcome_axes):
            raise ValueError("W8-06 cannot claim operational ready under the no-command contract")
        return self


__all__ = [name for name in globals() if name.startswith("BATCH_SCENARIO") or name.startswith("BatchScenario")]
