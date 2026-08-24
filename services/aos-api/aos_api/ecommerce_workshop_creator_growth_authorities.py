"""Canonical W2-04 creator candidate and match authorities."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext


class CreatorExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=100)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class MatchDisposition(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class CreatorCandidateRevision(AipContractModel):
    tenant: TenantContext
    candidate_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    identity_ref: CreatorExactRef
    profile_evidence_refs: list[CreatorExactRef] = Field(min_length=1, max_length=20)
    pii_refs: list[str] = Field(default_factory=list, max_length=20)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("candidate observedAt must include a timezone")
        return value

    @model_validator(mode="after")
    def _identity_integrity(self) -> CreatorCandidateRevision:
        if self.identity_ref.resource_type != "CreatorIdentityRevision":
            raise ValueError("identityRef must reference CreatorIdentityRevision")
        identities = [(item.resource_type, item.resource_id, item.revision) for item in self.profile_evidence_refs]
        if len(identities) != len(set(identities)):
            raise ValueError("profileEvidenceRefs must be unique")
        if len(self.pii_refs) != len(set(self.pii_refs)) or any(not item.strip() for item in self.pii_refs):
            raise ValueError("piiRefs must be unique opaque references")
        return self


class CreatorMatchObservation(AipContractModel):
    tenant: TenantContext
    observation_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    candidate_ref: CreatorExactRef
    policy_ref: CreatorExactRef
    evidence_refs: list[CreatorExactRef] = Field(min_length=1, max_length=30)
    score: float = Field(ge=0, le=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("match observation time must include a timezone")
        return value

    @model_validator(mode="after")
    def _typed_refs(self) -> CreatorMatchObservation:
        if self.candidate_ref.resource_type != "CreatorCandidateRevision":
            raise ValueError("candidateRef must reference CreatorCandidateRevision")
        if self.policy_ref.resource_type != "CreatorMatchPolicyRevision":
            raise ValueError("policyRef must reference CreatorMatchPolicyRevision")
        return self


class CreatorMatchDecision(AipContractModel):
    tenant: TenantContext
    decision_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    observation_ref: CreatorExactRef
    disposition: MatchDisposition
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    decided_by: str = Field(min_length=1, max_length=200)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    decided_at: datetime

    @field_validator("decided_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("match decision time must include a timezone")
        return value

    @model_validator(mode="after")
    def _observation_only(self) -> CreatorMatchDecision:
        if self.observation_ref.resource_type != "CreatorMatchObservation":
            raise ValueError("observationRef must reference CreatorMatchObservation")
        return self


__all__ = [
    "CreatorCandidateRevision",
    "CreatorExactRef",
    "CreatorMatchDecision",
    "CreatorMatchObservation",
    "MatchDisposition",
]
