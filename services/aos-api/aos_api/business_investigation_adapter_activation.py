"""Fail-closed per-platform activation decisions for investigation AdapterPacks."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.business_investigation_adapter_capability import AdapterPlatform
from aos_api.business_investigation_shared_contracts import InvestigationExactRef


MATRIX_SCHEMA = "aos.business-investigation.adapter-activation-matrix/v1"
DECISION_SCHEMA = "aos.business-investigation.adapter-activation-decision/v1"
SHA256 = r"^sha256:[0-9a-f]{64}$"


def _canonical_hash(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _exact(ref: InvestigationExactRef, expected: str, field: str) -> None:
    if ref.resource_type != expected:
        raise ValueError(f"{field} must reference {expected}")


def _same_tenant(left: TenantContext, right: TenantContext) -> bool:
    return left.org_id == right.org_id and left.project_id == right.project_id


class PlatformTermsStatus(StrEnum):
    UNVERIFIED = "unverified"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


class AdapterHealthStatus(StrEnum):
    UNKNOWN = "unknown"
    READY = "ready"
    STALE = "stale"
    FAILED = "failed"


class AdapterSourceReadinessState(StrEnum):
    UNKNOWN = "unknown"
    READY = "ready"
    STALE = "stale"
    BLOCKED = "blocked"


class AdapterActivationStatus(StrEnum):
    DISABLED = "disabled"
    ELIGIBLE_DRY_RUN_ONLY = "eligible_dry_run_only"


class PlatformTermsGate(AipContractModel):
    platform: AdapterPlatform
    tenant: TenantContext
    terms_ref: InvestigationExactRef
    acceptance_receipt_ref: InvestigationExactRef
    status: PlatformTermsStatus
    accepted_by: str | None = Field(default=None, min_length=1, max_length=160)
    accepted_at: datetime | None = None
    expires_at: datetime | None = None
    subject_id: str | None = Field(default=None, min_length=1, max_length=160)
    expected_subject_id: str = Field(min_length=1, max_length=160)

    @model_validator(mode="after")
    def _refs(self) -> Self:
        _exact(self.terms_ref, "PlatformTermsRevision", "termsRef")
        _exact(self.acceptance_receipt_ref, "PlatformTermsAcceptanceReceipt", "acceptanceReceiptRef")
        return self


class AdapterHealthGate(AipContractModel):
    platform: AdapterPlatform
    tenant: TenantContext
    health_receipt_ref: InvestigationExactRef
    status: AdapterHealthStatus
    passed_checks: int = Field(ge=0, le=3)
    required_checks: Literal[3]
    scoped_at_start: bool
    evaluated_at: datetime
    valid_until: datetime

    @model_validator(mode="after")
    def _ref(self) -> Self:
        _exact(self.health_receipt_ref, "AdapterHealthReceipt", "healthReceiptRef")
        return self


class AdapterSourceReadinessGate(AipContractModel):
    platform: AdapterPlatform
    tenant: TenantContext
    source_readiness_ref: InvestigationExactRef
    state: AdapterSourceReadinessState
    current: bool
    cutoff: datetime

    @model_validator(mode="after")
    def _ref(self) -> Self:
        _exact(self.source_readiness_ref, "SourceReadinessRevision", "sourceReadinessRef")
        return self


class AdapterActivationCandidate(AipContractModel):
    candidate_id: str = Field(min_length=1, max_length=160)
    source_kind: Literal["synthetic", "historical_redacted"]
    tenant: TenantContext
    platform: AdapterPlatform
    capability_ref: InvestigationExactRef
    profile_ref: InvestigationExactRef
    overlay_ref: InvestigationExactRef
    installation_ref: InvestigationExactRef
    version_ref: InvestigationExactRef
    capability_enabled: bool
    profile_enabled: bool
    overlay_enabled: bool
    installation_active: bool
    version_compatible: bool
    activation_authorized: bool
    terms: PlatformTermsGate
    health: AdapterHealthGate
    source_readiness: AdapterSourceReadinessGate
    candidate_hash: str = Field(pattern=SHA256)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        _exact(self.capability_ref, "AdapterCapabilityMatrixRevision", "capabilityRef")
        _exact(self.overlay_ref, "BusinessInvestigationInstanceOverlayRevision", "overlayRef")
        _exact(self.installation_ref, "AdapterInstallationLockRevision", "installationRef")
        _exact(self.version_ref, "AdapterPackVersionRevision", "versionRef")
        profile_types = {
            AdapterPlatform.NIUSHOP: "NiushopAdapterProfileRevision",
            AdapterPlatform.WECHAT_STORE: "WechatStoreAdapterProfileRevision",
            AdapterPlatform.DOUYIN_STORE: "DouyinStoreAdapterProfileRevision",
        }
        _exact(self.profile_ref, profile_types[self.platform], "profileRef")
        for name, gate in (("terms", self.terms), ("health", self.health), ("sourceReadiness", self.source_readiness)):
            if gate.platform != self.platform:
                raise ValueError(f"{name} platform must match candidate platform")
            if not _same_tenant(self.tenant, gate.tenant):
                raise ValueError(f"{name} tenant must match candidate tenant")
        return self

    def calculated_hash(self) -> str:
        value = self.model_dump(by_alias=True, mode="json")
        value.pop("candidateHash")
        return _canonical_hash(value)


class AdapterActivationMatrix(AipContractModel):
    schema_version: str = MATRIX_SCHEMA
    matrix_id: str = Field(min_length=1, max_length=160)
    revision: Literal[1]
    content_hash: str = Field(pattern=SHA256)
    candidates: list[AdapterActivationCandidate] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != MATRIX_SCHEMA:
            raise ValueError("unsupported Adapter activation matrix schema")
        if len({item.candidate_id for item in self.candidates}) != len(self.candidates):
            raise ValueError("activation candidate IDs must be unique")
        if set(item.platform for item in self.candidates) != set(AdapterPlatform):
            raise ValueError("activation matrix must cover all three platforms")
        tenants = {(item.tenant.org_id, item.tenant.project_id) for item in self.candidates}
        if len(tenants) != 1:
            raise ValueError("activation matrix candidates must share one tenant")
        return self

    def calculated_hash(self) -> str:
        value = self.model_dump(by_alias=True, mode="json")
        value.pop("contentHash")
        return _canonical_hash(value)


class AdapterActivationDecision(AipContractModel):
    schema_version: str = DECISION_SCHEMA
    status: AdapterActivationStatus
    candidate_ref: InvestigationExactRef | None
    platform: AdapterPlatform | None
    blockers: list[str]
    activation_executed: Literal[False]
    automatic_retry: Literal[False]
    external_effect: Literal[False]


def _terms_blockers(terms: PlatformTermsGate, evaluated_at: datetime) -> list[str]:
    if terms.status is PlatformTermsStatus.UNVERIFIED:
        return ["PLATFORM_TERMS_UNVERIFIED"]
    if terms.status is not PlatformTermsStatus.ACCEPTED:
        return ["PLATFORM_TERMS_NOT_CURRENT"]
    blockers: list[str] = []
    if terms.accepted_by is None or terms.accepted_at is None or terms.expires_at is None:
        blockers.append("PLATFORM_TERMS_ACCEPTANCE_INCOMPLETE")
    elif terms.expires_at <= evaluated_at:
        blockers.append("PLATFORM_TERMS_EXPIRED")
    if terms.subject_id != terms.expected_subject_id:
        blockers.append("PLATFORM_TERMS_SUBJECT_MISMATCH")
    return blockers


def _health_blockers(health: AdapterHealthGate, evaluated_at: datetime) -> list[str]:
    blockers: list[str] = []
    if health.status is not AdapterHealthStatus.READY or not health.scoped_at_start:
        blockers.append("HEALTH_NOT_READY")
    if health.passed_checks != health.required_checks:
        blockers.append("HEALTH_NOT_3_OF_3")
    if health.valid_until <= evaluated_at or health.evaluated_at > evaluated_at:
        blockers.append("HEALTH_STALE")
    return blockers


def _readiness_blockers(readiness: AdapterSourceReadinessGate) -> list[str]:
    blockers: list[str] = []
    if readiness.state is not AdapterSourceReadinessState.READY:
        blockers.append("SOURCE_READINESS_NOT_READY")
    if not readiness.current:
        blockers.append("SOURCE_READINESS_STALE")
    return blockers


def evaluate_activation_candidate(
    candidate: AdapterActivationCandidate,
    org_id: str,
    project_id: str,
    evaluated_at: datetime,
) -> AdapterActivationDecision:
    if candidate.tenant.org_id != org_id or candidate.tenant.project_id != project_id:
        return AdapterActivationDecision(
            status=AdapterActivationStatus.DISABLED,
            candidateRef=None,
            platform=None,
            blockers=["TENANT_SCOPE_MISMATCH"],
            activationExecuted=False,
            automaticRetry=False,
            externalEffect=False,
        )
    blockers = []
    if not candidate.capability_enabled:
        blockers.append("CAPABILITY_DISABLED")
    if not candidate.profile_enabled:
        blockers.append("PROFILE_DISABLED")
    if not candidate.overlay_enabled:
        blockers.append("OVERLAY_DISABLED")
    if not candidate.installation_active:
        blockers.append("INSTALLATION_INACTIVE")
    if not candidate.version_compatible:
        blockers.append("ADAPTER_VERSION_INCOMPATIBLE")
    blockers.extend(_terms_blockers(candidate.terms, evaluated_at))
    blockers.extend(_health_blockers(candidate.health, evaluated_at))
    blockers.extend(_readiness_blockers(candidate.source_readiness))
    if not candidate.activation_authorized:
        blockers.append("ACTIVATION_NOT_AUTHORIZED")
    return AdapterActivationDecision(
        status=AdapterActivationStatus.DISABLED if blockers else AdapterActivationStatus.ELIGIBLE_DRY_RUN_ONLY,
        candidateRef={
            "resourceType": "AdapterActivationCandidateRevision",
            "resourceId": candidate.candidate_id,
            "revision": 1,
            "contentHash": candidate.candidate_hash,
        },
        platform=candidate.platform,
        blockers=blockers,
        activationExecuted=False,
        automaticRetry=False,
        externalEffect=False,
    )


def evaluate_activation_matrix(
    matrix: AdapterActivationMatrix,
    org_id: str,
    project_id: str,
    evaluated_at: datetime,
) -> dict[str, AdapterActivationDecision]:
    for candidate in matrix.candidates:
        if candidate.calculated_hash() != candidate.candidate_hash:
            raise ValueError(f"candidate hash drifted: {candidate.candidate_id}")
    if matrix.calculated_hash() != matrix.content_hash:
        raise ValueError("activation matrix content hash drifted")
    return {
        candidate.platform.value: evaluate_activation_candidate(candidate, org_id, project_id, evaluated_at)
        for candidate in sorted(matrix.candidates, key=lambda item: item.platform.value)
    }
