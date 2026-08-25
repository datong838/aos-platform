"""W5-07 canonical Action Kill, Canary plan and drill contracts."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, ResourceRef
from aos_api.aip_production_contracts import ExactRevisionRef

KillPolicyLevel = Literal[
    "org", "project", "account", "adapter", "capability", "action_type"
]


class ProposeKillPolicyRequest(AipContractModel):
    policy_id: str
    expected_head_version: int = Field(ge=0)
    level: KillPolicyLevel
    kill_enabled: bool
    reason_code: str
    account_binding_ref: ExactRevisionRef | None = None
    adapter_revision_ref: ExactRevisionRef | None = None
    capability_binding_ref: ExactRevisionRef | None = None
    action_type_id: str | None = None
    valid_from: datetime
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def _exact_scope(self) -> "ProposeKillPolicyRequest":
        expected = {
            "account": self.account_binding_ref,
            "adapter": self.adapter_revision_ref,
            "capability": self.capability_binding_ref,
            "action_type": self.action_type_id,
        }
        if self.level in expected and expected[self.level] is None:
            raise ValueError(f"{self.level} policy requires its exact scope")
        for level, value in expected.items():
            if self.level != level and value is not None:
                raise ValueError(f"{level} exact scope is not valid for {self.level} policy")
        expected_types = {
            "account": "AccountBindingRevision",
            "adapter": "AdapterCapabilityRevision",
            "capability": "CapabilityBindingRevision",
        }
        scoped_ref = expected.get(self.level)
        if self.level in expected_types and scoped_ref.resource_type != expected_types[self.level]:
            raise ValueError(f"{self.level} policy requires {expected_types[self.level]}")
        if self.expires_at is not None and self.expires_at <= self.valid_from:
            raise ValueError("expiresAt must be after validFrom")
        if not self.policy_id.strip() or not self.reason_code.strip():
            raise ValueError("policyId and reasonCode are required")
        return self


class DecideKillPolicyRequest(AipContractModel):
    expected_head_version: int = Field(ge=0)
    expected_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: Literal["approved", "rejected"]
    reason: str


class KillPolicyRevisionSnapshot(AipContractModel):
    policy_id: str
    revision: int = Field(ge=1)
    head_version: int = Field(ge=0)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    level: KillPolicyLevel
    kill_enabled: bool
    reason_code: str
    account_binding_ref: ExactRevisionRef | None = None
    adapter_revision_ref: ExactRevisionRef | None = None
    capability_binding_ref: ExactRevisionRef | None = None
    action_type_id: str | None = None
    valid_from: datetime
    expires_at: datetime | None = None
    proposed_by: str
    active: bool
    decision: Literal["approved", "rejected"] | None = None
    created_at: datetime


class EvaluateKillPolicyRequest(AipContractModel):
    action_type_id: str
    account_binding_ref: ExactRevisionRef | None = None
    adapter_revision_ref: ExactRevisionRef | None = None
    capability_binding_ref: ExactRevisionRef | None = None


class EffectiveKillDecision(AipContractModel):
    blocked: bool
    reason_codes: list[str] = Field(default_factory=list)
    policy_refs: list[ExactRevisionRef] = Field(default_factory=list)
    evaluated_at: datetime


class ProposeCanaryPlanRequest(AipContractModel):
    plan_id: str
    action_type_revision_ref: ExactRevisionRef
    capability_binding_ref: ExactRevisionRef
    account_binding_ref: ExactRevisionRef
    adapter_revision_ref: ExactRevisionRef
    object_ref: ResourceRef
    max_quantity: int = Field(ge=1, le=10)
    max_budget: Decimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    window_starts_at: datetime
    window_ends_at: datetime
    operator_id: str
    stop_conditions: list[str] = Field(min_length=1)

    @field_validator("currency")
    @classmethod
    def _currency(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def _bounded(self) -> "ProposeCanaryPlanRequest":
        if self.window_ends_at <= self.window_starts_at:
            raise ValueError("windowEndsAt must be after windowStartsAt")
        if not self.plan_id.strip() or not self.operator_id.strip():
            raise ValueError("planId and operatorId are required")
        exact_types = (
            (self.action_type_revision_ref, "ActionTypeRevision"),
            (self.capability_binding_ref, "CapabilityBindingRevision"),
            (self.account_binding_ref, "AccountBindingRevision"),
            (self.adapter_revision_ref, "AdapterCapabilityRevision"),
        )
        if any(ref.resource_type != expected for ref, expected in exact_types):
            raise ValueError("Canary plan exact revision resource types are invalid")
        if len(set(self.stop_conditions)) != len(self.stop_conditions):
            raise ValueError("stopConditions must be unique")
        return self


class DecideCanaryPlanRequest(AipContractModel):
    expected_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: Literal["approved", "rejected"]
    reason: str


class CanaryPlanSnapshot(AipContractModel):
    plan_id: str
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["awaiting_approval", "approved", "rejected"]
    exact_scope: dict[str, Any]
    max_quantity: int
    max_budget: Decimal
    currency: str
    window_starts_at: datetime
    window_ends_at: datetime
    operator_id: str
    stop_conditions: list[str]
    proposed_by: str
    created_at: datetime


class SimulateKillDrillRequest(AipContractModel):
    policy_ref: ExactRevisionRef
    synthetic_new_dispatch_ids: list[str] = Field(min_length=1, max_length=20)
    inflight_attempt_ids: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _unique_ids(self) -> "SimulateKillDrillRequest":
        if self.policy_ref.resource_type != "KillPolicyRevision":
            raise ValueError("policyRef must be a KillPolicyRevision")
        if len(set(self.synthetic_new_dispatch_ids)) != len(self.synthetic_new_dispatch_ids):
            raise ValueError("syntheticNewDispatchIds must be unique")
        if len(set(self.inflight_attempt_ids)) != len(self.inflight_attempt_ids):
            raise ValueError("inflightAttemptIds must be unique")
        return self


class KillDrillReceiptSnapshot(AipContractModel):
    receipt_id: str
    policy_ref: ExactRevisionRef
    simulation_only: Literal[True]
    blocked_new_dispatches: list[str]
    inflight_reconcile_attempts: list[str]
    invariants: dict[str, Any]
    result: Literal["passed", "failed"]
    actor_id: str
    created_at: datetime
