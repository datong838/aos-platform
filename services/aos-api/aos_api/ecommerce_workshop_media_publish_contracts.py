"""Strict GET-only W7-10 media publication contribution contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel


MEDIA_PUBLISH_SCHEMA_VERSION = "aos.ecommerce-workshop.media-publish-contribution/v1"


class MediaPublishExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class MediaPublishCandidateContribution(AipContractModel):
    family_id: str = Field(min_length=1, max_length=200)
    family_version: int = Field(ge=1)
    variant_ref: MediaPublishExactRef
    gate_set_ref: MediaPublishExactRef
    platform: str = Field(min_length=1, max_length=120)
    profile: str = Field(min_length=1, max_length=120)


class MediaPublishImpactContribution(AipContractModel):
    preview_ref: MediaPublishExactRef
    action_binding_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    readiness: Literal["ready", "blocked"]
    expires_at: datetime
    atomic_skill_refs: list[MediaPublishExactRef] = Field(default_factory=list, max_length=64)
    logic_ref: MediaPublishExactRef
    colleague_binding_refs: list[MediaPublishExactRef] = Field(default_factory=list, max_length=64)

    @field_validator("expires_at")
    @classmethod
    def _aware_expiry(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("impact expiry requires timezone")
        return value


class MediaPublishActionContribution(AipContractModel):
    proposal_id: str = Field(min_length=1, max_length=200)
    proposal_version: int = Field(ge=1)
    proposal_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: str = Field(min_length=1, max_length=80)
    action_binding_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_count: int = Field(ge=0)
    lease_id: str | None = Field(default=None, min_length=1, max_length=200)
    attempt_id: str | None = Field(default=None, min_length=1, max_length=200)


class MediaPublishReceiptContribution(AipContractModel):
    receipt_id: str = Field(min_length=1, max_length=200)
    receipt_kind: str = Field(min_length=1, max_length=80)
    status: str = Field(min_length=1, max_length=80)
    provider_outcome: str | None = Field(default=None, max_length=80)
    reconciliation_status: str = Field(min_length=1, max_length=80)
    request_fingerprint: str = Field(min_length=1, max_length=256)
    response_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    action_binding_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    usage_receipt_count: int = Field(ge=0)
    lineage_attached: bool


class MediaPublishHandoffRequirement(AipContractModel):
    status: Literal["not_required", "required", "unresolved"]
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    required_facts: list[str] = Field(default_factory=list, max_length=20)
    minimal_disclosure: Literal[True] = True
    completion_receipt_required: Literal[True] = True
    completion_allowed: Literal[False] = False


class MediaPublishContribution(AipContractModel):
    schema_version: Literal[MEDIA_PUBLISH_SCHEMA_VERSION] = MEDIA_PUBLISH_SCHEMA_VERSION
    candidate: MediaPublishCandidateContribution
    impact: MediaPublishImpactContribution
    action: MediaPublishActionContribution
    receipt: MediaPublishReceiptContribution | None = None
    handoff: MediaPublishHandoffRequirement
    blocker_codes: list[str] = Field(default_factory=list, max_length=64)
    external_effects_allowed: Literal[False] = False

    @model_validator(mode="after")
    def _one_binding_and_honest_outcome(self) -> "MediaPublishContribution":
        bindings = {self.impact.action_binding_hash, self.action.action_binding_hash}
        if self.receipt is not None:
            bindings.add(self.receipt.action_binding_hash)
        if len(bindings) != 1:
            raise ValueError("publish contribution requires one actionBindingHash")
        if self.receipt is None and self.handoff.status == "not_required":
            raise ValueError("missing receipt requires a handoff requirement")
        if self.receipt is not None and self.receipt.provider_outcome in {"unknown", "partial"} and self.handoff.status == "not_required":
            raise ValueError("uncertain receipt requires a handoff requirement")
        if self.blocker_codes != sorted(set(self.blocker_codes)):
            raise ValueError("publish blockers must be sorted and unique")
        return self


__all__ = [name for name in globals() if name.startswith("MEDIA_PUBLISH") or name.startswith("MediaPublish")]
