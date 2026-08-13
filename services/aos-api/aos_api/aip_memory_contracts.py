"""AIP-5 public contracts for governed memory and knowledge retrieval.

This module freezes DTOs only. Importing it never allocates a store, registers
routes, or turns the legacy in-memory engines into an authority.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, ArtifactRef, ResourceRef, TenantContext

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class RuntimeMemoryLayer(StrEnum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


class KnowledgeScope(StrEnum):
    PUBLIC_PACKAGE = "public_package"
    ORGANIZATION = "organization"
    WORKSPACE = "workspace"


class MemoryCandidateStatus(StrEnum):
    PENDING = "pending"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"
    APPROVED = "approved"
    PROMOTED = "promoted"


class MemoryItemStatus(StrEnum):
    ACTIVE = "active"
    STALE = "stale"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ArtifactPiiStatus(StrEnum):
    CLEAR = "clear"
    REDACTED = "redacted"
    CONTAINS_PII = "contains_pii"
    UNKNOWN = "unknown"


class LicensePolicyDecision(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    UNKNOWN = "unknown"


class KnowledgeSourceKind(StrEnum):
    AUTHORIZED_DOCUMENT = "authorized_document"
    TASK_EVIDENCE = "task_evidence"
    EFFECT_REVIEW = "effect_review"
    RESEARCH_ARTIFACT = "research_artifact"
    PROFESSIONAL_DATABASE = "professional_database"
    CUSTOMER_AGGREGATE = "customer_aggregate"
    HUMAN_EXPERIENCE = "human_experience"


class KnowledgeSourceRef(AipContractModel):
    source_kind: KnowledgeSourceKind
    source_uri: str | None = Field(default=None, max_length=2048)
    source_ref: ResourceRef | None = None
    observed_at: datetime
    freshness_expires_at: datetime
    license_id: str = Field(min_length=1, max_length=200)
    usage_policy: str = Field(min_length=1, max_length=200)
    content_hash: str = Field(pattern=SHA256_PATTERN)
    provider: str = Field(min_length=1, max_length=200)
    provider_version: str = Field(min_length=1, max_length=120)
    applicability: list[str] = Field(min_length=1, max_length=64)

    @field_validator("license_id", "usage_policy", "provider", "provider_version")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("knowledge source governance fields must not be blank")
        return cleaned

    @field_validator("applicability")
    @classmethod
    def _unique_applicability(cls, value: list[str]) -> list[str]:
        cleaned = [entry.strip() for entry in value]
        if any(not entry for entry in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("applicability must contain unique non-blank values")
        return cleaned

    @model_validator(mode="after")
    def _source_and_freshness(self) -> KnowledgeSourceRef:
        if (self.source_uri is None) == (self.source_ref is None):
            raise ValueError("exactly one source_uri or source_ref is required")
        if self.freshness_expires_at <= self.observed_at:
            raise ValueError("freshness_expires_at must follow observed_at")
        return self


class SubmitMemoryCandidateRequest(AipContractModel):
    candidate_layer: RuntimeMemoryLayer
    task_id: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    subject: ResourceRef
    payload: ArtifactRef
    source: KnowledgeSourceRef
    confidence: float = Field(ge=0.0, le=1.0)
    marking: list[str] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def _candidate_layer(self) -> SubmitMemoryCandidateRequest:
        if self.candidate_layer is RuntimeMemoryLayer.WORKING:
            raise ValueError("working memory is restored from Task/Checkpoint, not promoted")
        if not self.payload.revision or not self.payload.content_hash:
            raise ValueError("candidate payload requires exact revision/hash")
        return self


class GovernanceApprovalRef(AipContractModel):
    eval_report: ArtifactRef
    draft: ResourceRef
    approval_event: ResourceRef

    @model_validator(mode="after")
    def _exact_eval(self) -> GovernanceApprovalRef:
        if not self.eval_report.revision or not self.eval_report.content_hash:
            raise ValueError("governance requires exact eval report revision/hash")
        return self


class ArtifactGovernanceInspection(AipContractModel):
    artifact: ArtifactRef
    pii_status: ArtifactPiiStatus
    inspection_ref: ResourceRef
    redaction_receipt: ResourceRef | None = None

    @model_validator(mode="after")
    def _exact_artifact(self) -> ArtifactGovernanceInspection:
        if not self.artifact.revision or not self.artifact.content_hash:
            raise ValueError("artifact inspection requires exact revision/hash")
        if not self.inspection_ref.revision:
            raise ValueError("artifact inspection evidence requires a revision")
        if self.pii_status is ArtifactPiiStatus.REDACTED:
            if self.redaction_receipt is None or not self.redaction_receipt.revision:
                raise ValueError("redacted artifact requires an exact redaction receipt")
        return self


class MemoryCandidate(AipContractModel):
    tenant: TenantContext
    candidate_id: str = Field(min_length=1, max_length=200)
    status: MemoryCandidateStatus
    scope: KnowledgeScope
    request: SubmitMemoryCandidateRequest
    quarantine_reasons: list[str] = Field(default_factory=list)
    governance: GovernanceApprovalRef | None = None
    version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _status_evidence(self) -> MemoryCandidate:
        if self.status in {MemoryCandidateStatus.APPROVED, MemoryCandidateStatus.PROMOTED} and self.governance is None:
            raise ValueError("approved/promoted candidate requires governance evidence")
        if self.status is MemoryCandidateStatus.QUARANTINED and not self.quarantine_reasons:
            raise ValueError("quarantined candidate requires reasons")
        return self


class MemoryCandidateEvent(AipContractModel):
    tenant: TenantContext
    event_id: str = Field(min_length=1, max_length=200)
    candidate_id: str = Field(min_length=1, max_length=200)
    sequence: int = Field(ge=1)
    event_type: str = Field(pattern=r"^(submitted|quarantined|rejected|approved|promoted)$")
    from_status: MemoryCandidateStatus | None = None
    to_status: MemoryCandidateStatus
    reason_codes: list[str] = Field(default_factory=list)
    evidence_ref: ResourceRef | None = None
    event_hash: str = Field(pattern=SHA256_PATTERN)
    actor: str = Field(min_length=1, max_length=200)
    occurred_at: datetime

    @model_validator(mode="after")
    def _event_matches_status(self) -> MemoryCandidateEvent:
        expected = (
            "submitted"
            if self.to_status is MemoryCandidateStatus.PENDING
            else self.to_status.value
        )
        if self.event_type != expected:
            raise ValueError("candidate event type must match target status")
        if self.sequence == 1 and self.from_status is not None:
            raise ValueError("initial candidate event must not have from_status")
        return self


class MemoryItemRevision(AipContractModel):
    tenant: TenantContext
    memory_item_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    candidate_id: str = Field(min_length=1, max_length=200)
    source_id: str = Field(min_length=1, max_length=200)
    source_revision: int = Field(ge=1)
    payload: ArtifactRef
    content_hash: str = Field(pattern=SHA256_PATTERN)
    confidence: float = Field(ge=0.0, le=1.0)
    applicability: list[str] = Field(min_length=1)
    markings: list[str] = Field(min_length=1)
    effective_at: datetime
    expires_at: datetime | None = None
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @model_validator(mode="after")
    def _validity_window(self) -> MemoryItemRevision:
        if self.expires_at is not None and self.expires_at <= self.effective_at:
            raise ValueError("memory revision expiry must follow effective_at")
        return self


class MemoryItem(AipContractModel):
    tenant: TenantContext
    memory_item_id: str = Field(min_length=1, max_length=200)
    memory_layer: RuntimeMemoryLayer
    scope: KnowledgeScope
    status: MemoryItemStatus
    subject: ResourceRef
    current_revision: int = Field(ge=1)
    version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _persisted_layer(self) -> MemoryItem:
        if self.memory_layer is RuntimeMemoryLayer.WORKING:
            raise ValueError("working memory is restored from Task/Checkpoint")
        return self


class KnowledgeCitation(AipContractModel):
    memory_item_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    scope: KnowledgeScope
    subject: ResourceRef
    payload: ArtifactRef
    content_hash: str = Field(pattern=SHA256_PATTERN)
    source: KnowledgeSourceRef
    freshness: MemoryItemStatus
    confidence: float = Field(ge=0.0, le=1.0)
    applicability: list[str] = Field(min_length=1)
    markings: list[str] = Field(min_length=1)


class KnowledgeContextChunk(AipContractModel):
    citation: KnowledgeCitation
    content: str = Field(min_length=1)
    token_count: int = Field(ge=1)


class KnowledgeQuery(AipContractModel):
    subject: ResourceRef
    task_id: str = Field(min_length=1, max_length=200)
    skill_ref: ResourceRef
    object_refs: list[ResourceRef] = Field(default_factory=list, max_length=100)
    time_cutoff: datetime
    markings: list[str] = Field(min_length=1, max_length=32)
    max_tokens: int = Field(ge=64, le=32768)


class KnowledgeQueryResult(AipContractModel):
    citations: list[KnowledgeCitation]
    chunks: list[KnowledgeContextChunk] = Field(default_factory=list)
    status: str = Field(pattern=r"^(complete|degraded|blocked)$")
    blocked_reasons: list[str] = Field(default_factory=list)
    assembled_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def _blocked_is_empty(self) -> KnowledgeQueryResult:
        if self.status == "blocked" and (
            self.citations or self.chunks or not self.blocked_reasons
        ):
            raise ValueError("blocked result must contain reasons and no citations")
        if len(self.citations) != len(self.chunks) or any(
            citation != chunk.citation
            for citation, chunk in zip(self.citations, self.chunks)
        ):
            raise ValueError("context chunks must align exactly with citations")
        if self.assembled_tokens != sum(chunk.token_count for chunk in self.chunks):
            raise ValueError("assembled token count must equal context chunks")
        return self


class KnowledgeSearch(AipContractModel):
    query: str = Field(min_length=2, max_length=500)
    task_id: str = Field(min_length=1, max_length=200)
    skill_ref: ResourceRef
    time_cutoff: datetime
    markings: list[str] = Field(min_length=1, max_length=32)
    limit: int = Field(default=10, ge=1, le=50)
    max_tokens: int = Field(default=2048, ge=64, le=32768)

    @field_validator("query")
    @classmethod
    def _clean_query(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("knowledge search query is too short")
        return cleaned


class KnowledgeSearchLane(AipContractModel):
    lane: str = Field(pattern=r"^(fulltext|vector|rerank)$")
    status: str = Field(pattern=r"^(unbuilt|ready|degraded|blocked)$")
    reason_code: str | None = Field(default=None, min_length=1, max_length=200)
    provider: str | None = Field(default=None, min_length=1, max_length=200)
    provider_revision: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def _lane_shape(self) -> KnowledgeSearchLane:
        if self.status == "ready":
            if not self.provider or not self.provider_revision or self.reason_code:
                raise ValueError("ready search lane requires provider/revision and no reason")
        elif not self.reason_code:
            raise ValueError("non-ready search lane requires reason")
        return self


class KnowledgeSearchMatch(AipContractModel):
    citation: KnowledgeCitation
    chunk: KnowledgeContextChunk
    score: float = Field(ge=0.0)

    @model_validator(mode="after")
    def _citation_is_exact(self) -> KnowledgeSearchMatch:
        if self.chunk.citation != self.citation:
            raise ValueError("search match chunk must use the same citation")
        return self


class KnowledgeSearchResult(AipContractModel):
    matches: list[KnowledgeSearchMatch]
    lanes: list[KnowledgeSearchLane] = Field(min_length=3, max_length=3)
    status: str = Field(pattern=r"^(complete|degraded|blocked)$")
    blocked_reasons: list[str] = Field(default_factory=list)
    assembled_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def _result_shape(self) -> KnowledgeSearchResult:
        if [lane.lane for lane in self.lanes] != ["fulltext", "vector", "rerank"]:
            raise ValueError("search lanes must be ordered fulltext/vector/rerank")
        if self.status == "blocked" and (self.matches or not self.blocked_reasons):
            raise ValueError("blocked search result must be empty with reasons")
        if self.status != "blocked" and not self.matches:
            raise ValueError("non-blocked search result requires matches")
        if self.assembled_tokens != sum(match.chunk.token_count for match in self.matches):
            raise ValueError("assembled token count must equal search chunks")
        return self


__all__ = [
    "ArtifactGovernanceInspection",
    "ArtifactPiiStatus",
    "GovernanceApprovalRef",
    "KnowledgeCitation",
    "KnowledgeContextChunk",
    "KnowledgeQuery",
    "KnowledgeQueryResult",
    "KnowledgeSearch",
    "KnowledgeSearchLane",
    "KnowledgeSearchMatch",
    "KnowledgeSearchResult",
    "KnowledgeScope",
    "KnowledgeSourceKind",
    "KnowledgeSourceRef",
    "LicensePolicyDecision",
    "MemoryCandidate",
    "MemoryCandidateEvent",
    "MemoryCandidateStatus",
    "MemoryItem",
    "MemoryItemRevision",
    "MemoryItemStatus",
    "RuntimeMemoryLayer",
    "SubmitMemoryCandidateRequest",
]
