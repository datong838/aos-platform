"""W7-07 canonical media Provider Job and asset-safety contracts.

These contracts describe authority and read models only.  They never resolve a
secret, mint a URL, call a Provider, or treat ``submitted`` as delivery.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef


class MediaAssetDirection(StrEnum):
    INPUT = "input"
    OUTPUT = "output"


class MediaScanVerdict(StrEnum):
    PASSED = "passed"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class MediaJobStatus(StrEnum):
    PREPARED = "prepared"
    SUBMITTED = "submitted"
    RUNNING = "running"
    CANCEL_REQUESTED = "cancel_requested"
    UNKNOWN = "unknown"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MediaJobEventType(StrEnum):
    PREPARED = "prepared"
    SUBMITTED = "submitted"
    STATUS_OBSERVED = "status_observed"
    CANCEL_REQUESTED = "cancel_requested"
    RECONCILED = "reconciled"


class ProviderOperation(StrEnum):
    SUBMIT = "submit"
    STATUS = "status"
    WEBHOOK = "webhook"
    CANCEL = "cancel"
    RECONCILE = "reconcile"


class MediaSecurityFinding(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,119}$")
    location: str = Field(min_length=1, max_length=240)
    evidence_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ServerOwnedMediaScanResult(AipContractModel):
    """Transient scanner result accepted only from a server-owned scanner."""

    detected_mime: str = Field(min_length=1, max_length=160)
    byte_size: int = Field(ge=0, le=10_000_000_000)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    verdict: MediaScanVerdict
    findings: list[MediaSecurityFinding] = Field(default_factory=list, max_length=100)
    scanned_at: datetime

    @model_validator(mode="after")
    def _honest_verdict(self) -> ServerOwnedMediaScanResult:
        if self.scanned_at.utcoffset() is None:
            raise ValueError("scan timestamp must be timezone-aware")
        if self.verdict is MediaScanVerdict.PASSED and self.findings:
            raise ValueError("passed scan cannot contain findings")
        if self.verdict is not MediaScanVerdict.PASSED and not self.findings:
            raise ValueError("non-passed scan requires findings")
        return self


class MediaScanObservation(AipContractModel):
    tenant: TenantContext
    scan_id: str = Field(min_length=1, max_length=200)
    artifact_ref: ExactRevisionRef
    direction: MediaAssetDirection
    scan_policy_ref: ExactRevisionRef
    detected_mime: str = Field(min_length=1, max_length=160)
    byte_size: int = Field(ge=0, le=10_000_000_000)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    verdict: MediaScanVerdict
    findings: list[MediaSecurityFinding] = Field(default_factory=list, max_length=100)
    scanner_ref: ExactRevisionRef
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @model_validator(mode="after")
    def _exact_kinds(self) -> MediaScanObservation:
        if self.artifact_ref.resource_type != "Artifact":
            raise ValueError("scan artifact_ref must reference Artifact")
        if self.scan_policy_ref.resource_type != "MediaAssetScanPolicyRevision":
            raise ValueError("scan policy ref kind drifted")
        if self.scanner_ref.resource_type != "MediaAssetScannerRevision":
            raise ValueError("scanner ref kind drifted")
        return self


class MediaProviderBindingSnapshot(AipContractModel):
    capability_ref: ExactRevisionRef
    binding_ref: ExactRevisionRef
    model_route_ref: ExactRevisionRef
    model_ref: ExactRevisionRef
    provider_ref: ExactRevisionRef
    runtime_policy_ref: ExactRevisionRef
    provider_plugin_ref: ExactRevisionRef
    price_snapshot_ref: ExactRevisionRef
    adapter_ref: ExactRevisionRef
    license_ref: ExactRevisionRef
    eval_gate_ref: ExactRevisionRef

    @model_validator(mode="after")
    def _exact_kinds(self) -> MediaProviderBindingSnapshot:
        expected = {
            "capability_ref": "CapabilityRevision",
            "binding_ref": "CapabilityBindingRevision",
            "model_route_ref": "ModelRouteRevision",
            "model_ref": "RegisteredModelRevision",
            "provider_ref": "ProviderInstanceRevision",
            "runtime_policy_ref": "RuntimePolicyRevision",
            "provider_plugin_ref": "ProviderPluginRevision",
            "price_snapshot_ref": "ModelPriceSnapshotRevision",
            "adapter_ref": "MediaProviderAdapterRevision",
            "license_ref": "MediaLicenseDecision",
            "eval_gate_ref": "EvalGateDecision",
        }
        for field_name, kind in expected.items():
            if getattr(self, field_name).resource_type != kind:
                raise ValueError(f"{field_name} must reference {kind}")
        return self


class PrepareMediaProviderJobRequest(AipContractModel):
    task_run_ref: ExactRevisionRef
    step_run_ref: ExactRevisionRef
    capability_ref: ExactRevisionRef
    binding_ref: ExactRevisionRef
    model_route_ref: ExactRevisionRef
    runtime_policy_ref: ExactRevisionRef
    adapter_ref: ExactRevisionRef
    license_ref: ExactRevisionRef
    scan_policy_ref: ExactRevisionRef
    scanner_ref: ExactRevisionRef
    input_artifact_refs: list[ExactRevisionRef] = Field(min_length=1, max_length=32)
    expected_output_modality: str = Field(pattern=r"^(image|audio|video)$")
    purpose: str = Field(min_length=1, max_length=240)
    data_classification: str = Field(pattern=r"^(public|internal|confidential|restricted)$")

    @field_validator("input_artifact_refs")
    @classmethod
    def _unique_inputs(cls, values: list[ExactRevisionRef]) -> list[ExactRevisionRef]:
        if any(item.resource_type != "Artifact" for item in values):
            raise ValueError("media inputs must reference Artifact")
        keys = [(item.resource_id, item.revision, item.content_hash) for item in values]
        if len(keys) != len(set(keys)):
            raise ValueError("media input refs must be unique")
        return values

    @model_validator(mode="after")
    def _request_kinds(self) -> PrepareMediaProviderJobRequest:
        expected = {
            "task_run_ref": "TaskRun",
            "step_run_ref": "StepRunAttempt",
            "capability_ref": "CapabilityRevision",
            "binding_ref": "CapabilityBindingRevision",
            "model_route_ref": "ModelRouteRevision",
            "runtime_policy_ref": "RuntimePolicyRevision",
            "adapter_ref": "MediaProviderAdapterRevision",
            "license_ref": "MediaLicenseDecision",
            "scan_policy_ref": "MediaAssetScanPolicyRevision",
            "scanner_ref": "MediaAssetScannerRevision",
        }
        for field_name, kind in expected.items():
            if getattr(self, field_name).resource_type != kind:
                raise ValueError(f"{field_name} must reference {kind}")
        return self


class MediaProviderJob(AipContractModel):
    tenant: TenantContext
    job_id: str = Field(min_length=1, max_length=200)
    task_run_ref: ExactRevisionRef
    step_run_ref: ExactRevisionRef
    binding: MediaProviderBindingSnapshot
    input_artifact_refs: list[ExactRevisionRef]
    input_scan_refs: list[ExactRevisionRef]
    scan_policy_ref: ExactRevisionRef
    scanner_ref: ExactRevisionRef
    expected_output_modality: str
    purpose: str
    data_classification: str
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: MediaJobStatus
    sequence: int = Field(ge=1)
    blocker_codes: list[str] = Field(default_factory=list, max_length=64)
    created_by: str
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _status_is_honest(self) -> MediaProviderJob:
        if self.scan_policy_ref.resource_type != "MediaAssetScanPolicyRevision":
            raise ValueError("scan_policy_ref must reference MediaAssetScanPolicyRevision")
        if self.scanner_ref.resource_type != "MediaAssetScannerRevision":
            raise ValueError("scanner_ref must reference MediaAssetScannerRevision")
        if self.status not in {MediaJobStatus.UNKNOWN, MediaJobStatus.FAILED} and self.blocker_codes:
            raise ValueError("non-blocked media status cannot contain blockers")
        if self.status in {MediaJobStatus.UNKNOWN, MediaJobStatus.FAILED} and not self.blocker_codes:
            raise ValueError("unknown/failed media status requires blockers")
        return self


class MediaProviderJobEvent(AipContractModel):
    tenant: TenantContext
    job_id: str
    sequence: int = Field(ge=1)
    event_type: MediaJobEventType
    status: MediaJobStatus
    provider_receipt_ref: ExactRevisionRef | None = None
    blocker_codes: list[str] = Field(default_factory=list, max_length=64)
    event_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    actor: str
    created_at: datetime


class ProviderOperationResult(AipContractModel):
    status: MediaJobStatus
    provider_request_id_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    output_artifact_refs: list[ExactRevisionRef] = Field(default_factory=list, max_length=32)
    usage_receipt_ref: ExactRevisionRef | None = None
    blocker_codes: list[str] = Field(default_factory=list, max_length=64)
    observed_at: datetime

    @model_validator(mode="after")
    def _result_shape(self) -> ProviderOperationResult:
        if self.observed_at.utcoffset() is None:
            raise ValueError("provider observation must be timezone-aware")
        if self.status in {MediaJobStatus.UNKNOWN, MediaJobStatus.FAILED} and not self.blocker_codes:
            raise ValueError("unknown/failed operation requires blocker codes")
        if self.status not in {MediaJobStatus.UNKNOWN, MediaJobStatus.FAILED} and self.blocker_codes:
            raise ValueError("non-blocked operation cannot contain blocker codes")
        if self.status is MediaJobStatus.SUCCEEDED and not self.output_artifact_refs:
            raise ValueError("succeeded provider operation requires output artifacts")
        if self.status is not MediaJobStatus.SUCCEEDED and self.output_artifact_refs:
            raise ValueError("only succeeded provider operation may expose output artifacts")
        if any(item.resource_type != "Artifact" for item in self.output_artifact_refs):
            raise ValueError("provider outputs must reference Artifact")
        return self


class MediaProviderReceipt(AipContractModel):
    tenant: TenantContext
    receipt_id: str
    job_id: str
    operation: ProviderOperation
    outcome: MediaJobStatus
    provider_request_id_hash: str | None = None
    output_artifact_refs: list[ExactRevisionRef] = Field(default_factory=list)
    usage_receipt_ref: ExactRevisionRef | None = None
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    actor: str
    observed_at: datetime


class MediaAccessGrant(AipContractModel):
    tenant: TenantContext
    grant_id: str
    artifact_ref: ExactRevisionRef
    principal_ref: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=1, max_length=240)
    marking: str = Field(min_length=1, max_length=80)
    license_ref: ExactRevisionRef
    expires_at: datetime
    token_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    access_receipt_ref: ExactRevisionRef
    created_at: datetime

    @model_validator(mode="after")
    def _grant_is_safe(self) -> MediaAccessGrant:
        if self.artifact_ref.resource_type != "Artifact":
            raise ValueError("access grant must reference Artifact")
        if self.license_ref.resource_type != "MediaLicenseDecision":
            raise ValueError("access grant license kind drifted")
        if self.access_receipt_ref.resource_type != "AccessReceipt":
            raise ValueError("access receipt kind drifted")
        if self.expires_at <= self.created_at:
            raise ValueError("access grant must expire after creation")
        return self


class IssueMediaAccessGrantRequest(AipContractModel):
    artifact_ref: ExactRevisionRef
    principal_ref: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=1, max_length=240)
    marking: str = Field(min_length=1, max_length=80)
    license_ref: ExactRevisionRef
    expires_at: datetime
    access_receipt_ref: ExactRevisionRef

    @model_validator(mode="after")
    def _safe_request(self) -> IssueMediaAccessGrantRequest:
        if self.artifact_ref.resource_type != "Artifact":
            raise ValueError("access grant artifact kind drifted")
        if self.license_ref.resource_type != "MediaLicenseDecision":
            raise ValueError("access grant license kind drifted")
        if self.access_receipt_ref.resource_type != "AccessReceipt":
            raise ValueError("access grant receipt kind drifted")
        if self.expires_at.utcoffset() is None:
            raise ValueError("access grant expiry must be timezone-aware")
        return self


class MediaProviderJobListResponse(AipContractModel):
    tenant: TenantContext
    items: list[MediaProviderJob]
    count: int = Field(ge=0)

    @model_validator(mode="after")
    def _count(self) -> MediaProviderJobListResponse:
        if self.count != len(self.items):
            raise ValueError("media job count drifted")
        return self


__all__ = [name for name in globals() if name.startswith("Media") or name.startswith("Prepare") or name.startswith("Provider") or name.startswith("ServerOwned")]
