"""C1 ResearchJob public adapter contract and fail-closed event reconciliation."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Protocol

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import (
    AipContractModel,
    ArtifactRef,
    ResourceRef,
    TenantContext,
)


class ResearchJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class ResearchProviderStatus(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class ResearchDeliveryStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN = "unknown"
    RECONCILED = "reconciled"


class ResearchJobManifest(AipContractModel):
    task_run_ref: ResourceRef
    lineage_ref: ResourceRef
    provider: str
    binding_revision: str
    manifest_hash: str
    idempotency_key: str
    budget: dict[str, Any] = Field(default_factory=dict)
    scoped_refs: list[ResourceRef] = Field(default_factory=list)
    output_schema_hash: str
    traceparent: str
    deadline: datetime

    @field_validator("provider", "binding_revision", "idempotency_key", "traceparent")
    @classmethod
    def _required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("research manifest fields must not be empty")
        return cleaned

    @field_validator("manifest_hash", "output_schema_hash")
    @classmethod
    def _hash(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(
            ch not in "0123456789abcdef" for ch in normalized
        ):
            raise ValueError("research hashes must be sha256 hex digests")
        return normalized

    @model_validator(mode="after")
    def _future_deadline(self) -> ResearchJobManifest:
        if self.deadline.tzinfo is None:
            raise ValueError("research deadline must include a timezone")
        return self

    @model_validator(mode="after")
    def _exact_lineage(self) -> ResearchJobManifest:
        ref = self.lineage_ref
        try:
            revision = int(ref.revision or "")
        except ValueError as exc:
            raise ValueError("research lineage revision must be a positive sequence") from exc
        if (
            ref.resource_type != "aip.lineage"
            or ref.authority != "aos.lineage"
            or revision < 1
        ):
            raise ValueError(
                "research lineage_ref must bind an exact aos.lineage sequence"
            )
        return self


class RegisterResearchProviderRequest(AipContractModel):
    provider_id: str
    revision: int = Field(ge=1)
    adapter_kind: str
    capability_ref: ResourceRef
    contract_hash: str
    callback_secret_ref_hash: str
    status: ResearchProviderStatus = ResearchProviderStatus.ENABLED

    @field_validator("provider_id", "adapter_kind")
    @classmethod
    def _provider_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("provider fields must not be empty")
        return cleaned

    @field_validator("contract_hash", "callback_secret_ref_hash")
    @classmethod
    def _provider_hash(cls, value: str) -> str:
        return _sha256(value, "provider hashes")

    @model_validator(mode="after")
    def _exact_capability(self) -> RegisterResearchProviderRequest:
        if (
            self.capability_ref.resource_type != "capability"
            or not self.capability_ref.revision
        ):
            raise ValueError(
                "provider capability_ref must be an exact capability revision"
            )
        return self


class ResearchProviderRevision(AipContractModel):
    tenant: TenantContext
    provider_id: str
    revision: int
    adapter_kind: str
    capability_ref: ResourceRef
    contract_hash: str
    callback_secret_ref_hash: str
    status: ResearchProviderStatus
    source_hash: str
    created_by: str
    created_at: datetime


class CreateResearchJobRequest(AipContractModel):
    run_id: str
    step_key: str
    provider_id: str
    provider_revision: int = Field(ge=1)
    manifest: ResearchJobManifest

    @field_validator("run_id", "step_key", "provider_id")
    @classmethod
    def _job_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("research job fields must not be empty")
        return cleaned


class ResearchJobSnapshot(AipContractModel):
    tenant: TenantContext
    job_id: str
    run_id: str
    plan_revision_id: str
    step_key: str
    provider_id: str
    provider_revision: int
    capability_ref: ResourceRef
    lineage_ref: ResourceRef
    manifest_hash: str
    output_schema_hash: str
    status: ResearchJobStatus
    provider_execution_id: str | None = None
    last_sequence: int = 0
    has_gap: bool = False
    created_at: datetime
    cancel_requested: bool = False
    resumability: str = Field(default="unsupported", pattern=r"^(unsupported|supported)$")
    retry_of_job_id: str | None = None


class CancelResearchJobRequest(AipContractModel):
    reason: str = Field(default="cancelled_by_operator", min_length=1, max_length=500)


class RetryResearchJobRequest(AipContractModel):
    """Create a new job; never resumes the original Provider execution."""

    idempotency_key: str = Field(min_length=1, max_length=160)
    reason: str = Field(default="retry_after_failure", min_length=1, max_length=500)


class ResearchJobListResponse(AipContractModel):
    tenant: TenantContext
    items: list[ResearchJobSnapshot]
    count: int = Field(ge=0)


class ResearchJobSubmission(AipContractModel):
    provider_execution_id: str
    provider_version: str
    accepted_manifest_hash: str


class RecordResearchSubmissionRequest(ResearchJobSubmission):
    job_id: str
    source_hash: str
    observed_at: datetime

    @field_validator("source_hash", "accepted_manifest_hash")
    @classmethod
    def _submission_hash(cls, value: str) -> str:
        return _sha256(value, "submission hashes")


class ResearchSubmissionReceipt(RecordResearchSubmissionRequest):
    tenant: TenantContext
    submission_receipt_id: str
    created_at: datetime


class ResearchJobEvent(AipContractModel):
    provider_execution_id: str
    sequence: int = Field(ge=1)
    event_id: str
    status: ResearchJobStatus
    payload_hash: str
    observed_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("payload_hash")
    @classmethod
    def _payload_hash(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(
            ch not in "0123456789abcdef" for ch in normalized
        ):
            raise ValueError("payload_hash must be a sha256 hex digest")
        return normalized


class ResearchJobObservation(AipContractModel):
    provider_execution_id: str
    status: ResearchJobStatus
    last_sequence: int = Field(ge=0)
    event_ids: list[str] = Field(default_factory=list)
    has_gap: bool = False


class RecordResearchArtifactRequest(AipContractModel):
    job_id: str
    provider_execution_id: str
    artifact_type: str
    content_ref: str
    media_type: str
    content_hash: str
    schema_ref: str | None = None
    source_hash: str
    observed_at: datetime

    @field_validator(
        "job_id", "provider_execution_id", "artifact_type", "content_ref", "media_type"
    )
    @classmethod
    def _artifact_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("artifact fields must not be empty")
        return cleaned

    @field_validator("content_hash", "source_hash")
    @classmethod
    def _artifact_hash(cls, value: str) -> str:
        return _sha256(value, "artifact hashes")


class ResearchArtifactReceipt(AipContractModel):
    tenant: TenantContext
    artifact_receipt_id: str
    artifact: ArtifactRef
    job_id: str
    provider_execution_id: str
    content_ref: str
    media_type: str
    source_hash: str
    observed_at: datetime
    created_at: datetime


class RecordResearchDeliveryRequest(AipContractModel):
    job_id: str
    provider_execution_id: str
    status: ResearchDeliveryStatus
    artifact_ids: list[str] = Field(default_factory=list)
    source_hash: str
    observed_at: datetime

    @field_validator("source_hash")
    @classmethod
    def _delivery_hash(cls, value: str) -> str:
        return _sha256(value, "delivery source_hash")

    @model_validator(mode="after")
    def _delivery_shape(self) -> RecordResearchDeliveryRequest:
        if self.status is ResearchDeliveryStatus.RECONCILED:
            raise ValueError("reconciled status requires a reconcile receipt")
        if self.status is ResearchDeliveryStatus.SUCCEEDED and not self.artifact_ids:
            raise ValueError("succeeded delivery requires artifact_ids")
        if self.status is not ResearchDeliveryStatus.SUCCEEDED and self.artifact_ids:
            raise ValueError("only succeeded delivery may bind artifact_ids")
        return self


class ReconcileResearchJobRequest(AipContractModel):
    job_id: str
    final_status: ResearchJobStatus
    reason_code: str
    source_hash: str
    observed_at: datetime

    @field_validator("reason_code")
    @classmethod
    def _reason_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("reason_code must not be empty")
        return cleaned

    @field_validator("source_hash")
    @classmethod
    def _reconcile_hash(cls, value: str) -> str:
        return _sha256(value, "reconcile source_hash")

    @model_validator(mode="after")
    def _terminal_status(self) -> ReconcileResearchJobRequest:
        if self.final_status not in _TERMINAL:
            raise ValueError("reconcile final_status must be terminal")
        return self


class ResearchDeliveryReceipt(AipContractModel):
    tenant: TenantContext
    receipt_id: str
    job_id: str
    receipt_kind: str
    status: str
    artifact_ids: list[str] = Field(default_factory=list)
    reason_code: str | None = None
    source_hash: str
    observed_at: datetime
    created_at: datetime


class ResearchJobAdapter(Protocol):
    """Provider contract. Implementations are registered later; none is selected by default."""

    def submit(self, manifest: ResearchJobManifest) -> ResearchJobSubmission: ...

    def status(self, provider_execution_id: str) -> ResearchJobStatus: ...

    def events(
        self, provider_execution_id: str, after_sequence: int
    ) -> list[ResearchJobEvent]: ...

    def artifacts(self, provider_execution_id: str) -> list[ArtifactRef]: ...

    def cancel(self, provider_execution_id: str) -> ResearchJobStatus: ...

    def health(self) -> dict[str, Any]: ...


_TERMINAL = {
    ResearchJobStatus.SUCCEEDED,
    ResearchJobStatus.FAILED,
    ResearchJobStatus.CANCELLED,
}
_ALLOWED = {
    ResearchJobStatus.QUEUED: {
        ResearchJobStatus.QUEUED,
        ResearchJobStatus.RUNNING,
        ResearchJobStatus.UNKNOWN,
    },
    ResearchJobStatus.RUNNING: {
        ResearchJobStatus.RUNNING,
        *_TERMINAL,
        ResearchJobStatus.UNKNOWN,
    },
    ResearchJobStatus.UNKNOWN: {ResearchJobStatus.UNKNOWN, *_TERMINAL},
    ResearchJobStatus.SUCCEEDED: {ResearchJobStatus.SUCCEEDED},
    ResearchJobStatus.FAILED: {ResearchJobStatus.FAILED},
    ResearchJobStatus.CANCELLED: {ResearchJobStatus.CANCELLED},
}


def reconcile_research_events(
    current: ResearchJobObservation,
    events: list[ResearchJobEvent],
) -> ResearchJobObservation:
    """Accept only contiguous, hash-valid, monotonic provider events."""
    seen = set(current.event_ids)
    status = current.status
    sequence = current.last_sequence
    accepted_ids = list(current.event_ids)
    has_gap = current.has_gap
    for event in sorted(events, key=lambda item: (item.sequence, item.event_id)):
        if event.provider_execution_id != current.provider_execution_id:
            raise ValueError("provider execution id changed during reconciliation")
        expected_hash = hashlib.sha256(_canonical_bytes(event.payload)).hexdigest()
        if not hmac.compare_digest(expected_hash, event.payload_hash):
            raise ValueError("provider event payload hash mismatch")
        if event.event_id in seen or event.sequence <= sequence:
            continue
        if event.sequence != sequence + 1:
            has_gap = True
            break
        if event.status not in _ALLOWED[status]:
            raise ValueError(
                f"research status cannot regress from {status} to {event.status}"
            )
        status = event.status
        sequence = event.sequence
        seen.add(event.event_id)
        accepted_ids.append(event.event_id)
    return ResearchJobObservation(
        provider_execution_id=current.provider_execution_id,
        status=status,
        last_sequence=sequence,
        event_ids=accepted_ids,
        has_gap=has_gap,
    )


def verify_research_callback(
    *,
    secret: bytes,
    timestamp: int,
    nonce: str,
    body: bytes,
    signature: str,
    seen_nonces: set[str],
    now: datetime | None = None,
    replay_window_seconds: int = 300,
) -> str:
    """Validate callback transport only; callers must still actively pull provider state."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("callback verification time must include timezone")
    if abs(int(current.timestamp()) - timestamp) > replay_window_seconds:
        raise ValueError("research callback is outside the replay window")
    if not nonce or nonce in seen_nonces:
        raise ValueError("research callback nonce was replayed")
    body_hash = hashlib.sha256(body).hexdigest()
    signed = f"{timestamp}.{nonce}.{body_hash}".encode()
    expected = hmac.new(secret, signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature.strip().lower()):
        raise ValueError("research callback signature mismatch")
    seen_nonces.add(nonce)
    return body_hash


def _canonical_bytes(value: Any) -> bytes:
    import json

    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_research_manifest_hash(manifest: ResearchJobManifest) -> str:
    payload = manifest.model_dump(mode="json", by_alias=True)
    payload.pop("manifestHash", None)
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _sha256(value: str, field_name: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ValueError(f"{field_name} must be sha256 hex digests")
    return normalized


RESEARCH_JOB_CONTRACT_MODELS = (
    ResearchProviderRevision,
    ResearchJobManifest,
    ResearchJobSubmission,
    ResearchJobEvent,
    ResearchJobObservation,
    ResearchJobSnapshot,
    ResearchArtifactReceipt,
    ResearchDeliveryReceipt,
)
