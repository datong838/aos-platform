"""Strict GET-only W8-02 PriceCase-rooted remedy scenario contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel


REMEDY_SCENARIO_SCHEMA_VERSION = "aos.ecommerce-workshop.remedy-scenario/v1"


class RemedyScenarioStageId(StrEnum):
    PRICE_OBSERVATION = "price_observation"
    MATCH_DECISION = "match_decision"
    PRICE_CASE = "price_case"
    AFFECTED_ORDERS = "affected_orders"
    OPERATION_CASE = "operation_case"
    CUSTOMER_HANDOFF = "customer_handoff"
    CONTACT_PERMIT = "contact_permit"
    ACTION_OUTCOMES = "action_outcomes"
    EFFECT_REVIEW = "effect_review"


class RemedyScenarioOutcomeAxisId(StrEnum):
    REPRICING = "repricing_applied"
    REFUND = "refund_compensation_submitted"
    MESSAGE = "customer_message_accepted"
    CASE = "operation_case_resolved"
    EFFECT = "effect_mature"


class RemedyScenarioExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class RemedyScenarioBlocker(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    dependency: str = Field(min_length=1, max_length=180)
    required_action: str = Field(min_length=1, max_length=500)


class RemedyScenarioStage(AipContractModel):
    stage_id: RemedyScenarioStageId
    status: Literal["ready", "blocked", "unknown"]
    exact_refs: list[RemedyScenarioExactRef] = Field(default_factory=list, max_length=60)
    contribution: str = Field(min_length=1, max_length=500)
    blockers: list[RemedyScenarioBlocker] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _honest_stage(self) -> "RemedyScenarioStage":
        identities = [(item.resource_type, item.resource_id, item.revision, item.content_hash) for item in self.exact_refs]
        if len(identities) != len(set(identities)):
            raise ValueError("remedy scenario stage refs must be unique")
        if self.status == "ready" and (not self.exact_refs or self.blockers):
            raise ValueError("ready remedy stage requires exact refs and no blockers")
        if self.status != "ready" and (self.exact_refs or not self.blockers):
            raise ValueError("non-ready remedy stage requires blockers and no trusted refs")
        return self


class RemedyScenarioConservationLedger(AipContractModel):
    affected_orders_expected: int = Field(ge=0)
    affected_orders_observed: int = Field(ge=0)
    eligible_customers_expected: int = Field(ge=0)
    eligible_customers_observed: int = Field(ge=0)
    actions_expected: int = Field(ge=0)
    actions_ready: int = Field(ge=0)
    actions_blocked: int = Field(ge=0)
    actions_unknown: int = Field(ge=0)

    @model_validator(mode="after")
    def _conserves(self) -> "RemedyScenarioConservationLedger":
        if self.affected_orders_observed > self.affected_orders_expected:
            raise ValueError("observed affected orders cannot exceed expected")
        if self.eligible_customers_observed > self.eligible_customers_expected:
            raise ValueError("observed eligible customers cannot exceed expected")
        if self.actions_expected != self.actions_ready + self.actions_blocked + self.actions_unknown:
            raise ValueError("remedy action outcomes must conserve denominator")
        return self


class RemedyScenarioOutcomeAxis(AipContractModel):
    axis_id: RemedyScenarioOutcomeAxisId
    status: Literal["ready", "blocked", "unknown"]
    exact_ref: RemedyScenarioExactRef | None = None
    blocker: RemedyScenarioBlocker | None = None

    @model_validator(mode="after")
    def _honest_axis(self) -> "RemedyScenarioOutcomeAxis":
        if self.status == "ready" and (self.exact_ref is None or self.blocker is not None):
            raise ValueError("ready remedy outcome requires exact ref")
        if self.status != "ready" and (self.exact_ref is not None or self.blocker is None):
            raise ValueError("non-ready remedy outcome requires one blocker")
        return self


class RemedyScenarioCommands(AipContractModel):
    reprice: Literal[False] = False
    refund_or_compensate: Literal[False] = False
    send_message: Literal[False] = False
    resolve_case: Literal[False] = False


class RemedyScenarioContribution(AipContractModel):
    schema_version: Literal[REMEDY_SCENARIO_SCHEMA_VERSION] = REMEDY_SCENARIO_SCHEMA_VERSION
    status: Literal["blocked"] = "blocked"
    root_case_ref: RemedyScenarioExactRef | None = None
    remedy_binding_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    evaluated_at: datetime
    stages: list[RemedyScenarioStage] = Field(min_length=9, max_length=9)
    ledger: RemedyScenarioConservationLedger
    outcome_axes: list[RemedyScenarioOutcomeAxis] = Field(min_length=5, max_length=5)
    blockers: list[RemedyScenarioBlocker] = Field(min_length=1, max_length=60)
    commands: RemedyScenarioCommands = Field(default_factory=RemedyScenarioCommands)
    protected_contact_resolved: Literal[False] = False
    external_effects_allowed: Literal[False] = False

    @field_validator("evaluated_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("remedy scenario evaluation requires timezone")
        return value

    @model_validator(mode="after")
    def _canonical_and_fail_closed(self) -> "RemedyScenarioContribution":
        if [item.stage_id for item in self.stages] != list(RemedyScenarioStageId):
            raise ValueError("remedy scenario stages require canonical order")
        if [item.axis_id for item in self.outcome_axes] != list(RemedyScenarioOutcomeAxisId):
            raise ValueError("remedy scenario outcome axes require canonical order")
        if (self.root_case_ref is None) != (self.remedy_binding_hash is None):
            raise ValueError("remedy scenario root and binding hash must appear together")
        if self.root_case_ref is not None and self.root_case_ref.resource_type != "PriceCaseRevision":
            raise ValueError("remedy scenario root must be PriceCaseRevision")
        price_case_stage = self.stages[list(RemedyScenarioStageId).index(RemedyScenarioStageId.PRICE_CASE)]
        if self.root_case_ref is not None and price_case_stage.status == "ready" and self.root_case_ref not in price_case_stage.exact_refs:
            raise ValueError("remedy root must be included in the ready price_case stage")
        if not any(item.status != "ready" for item in self.stages) and not any(item.status != "ready" for item in self.outcome_axes):
            raise ValueError("W8-02 cannot claim operational ready under the no-effect contract")
        return self


__all__ = [name for name in globals() if name.startswith("REMEDY_SCENARIO") or name.startswith("RemedyScenario")]
