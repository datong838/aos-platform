"""Strict BI-W3 contracts for bounded, read-only platform observation.

The models contain opaque runtime references only.  They never contain browser
credentials or session payloads, and importing this module cannot activate a
browser, Adapter, export or external side effect.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
import re
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.business_investigation_shared_contracts import (
    InvestigationBlocker,
    InvestigationExactRef,
    InvestigationPlatform,
)


OBSERVATION_SESSION_LEASE_SCHEMA_VERSION = (
    "aos.business-investigation.observation-session-lease/v1"
)
OBSERVATION_PLAN_SCHEMA_VERSION = "aos.business-investigation.observation-plan/v1"
OBSERVATION_RECEIPT_SCHEMA_VERSION = "aos.business-investigation.observation-receipt/v1"
SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
MAX_LEASE_DURATION = timedelta(hours=2)


def _aware(value: datetime, name: str) -> datetime:
    if value.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    return value


def _require_type(ref: InvestigationExactRef, expected: str, name: str) -> None:
    if ref.resource_type != expected:
        raise ValueError(f"{name} must reference {expected}")


def _unique(values: list[str], name: str) -> list[str]:
    cleaned = [item.strip() for item in values]
    if any(not item for item in cleaned) or len(cleaned) != len(set(cleaned)):
        raise ValueError(f"{name} must contain unique non-empty values")
    return cleaned


class ObservationReadAction(StrEnum):
    NAVIGATE = "navigate"
    WAIT = "wait"
    SCROLL = "scroll"
    FILTER = "filter"
    OPEN_DETAIL = "open-detail"
    READ = "read"
    EXPORT = "export"


class ObservationSessionLeaseStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class ObservationSessionLeaseRecord(AipContractModel):
    schema_version: str = OBSERVATION_SESSION_LEASE_SCHEMA_VERSION
    tenant: TenantContext
    lease_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    state_version: int = Field(ge=1)
    content_hash: str = Field(pattern=SHA256_PATTERN)
    platform: InvestigationPlatform
    channel_ref: InvestigationExactRef
    entity_ref: InvestigationExactRef
    requirement_ref: InvestigationExactRef
    purpose_code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,119}$")
    scope: Literal["read-only-observation"] = "read-only-observation"
    session_handle_ref: InvestigationExactRef
    allowed_domains: list[str] = Field(min_length=1, max_length=20)
    allowed_route_patterns: list[str] = Field(min_length=1, max_length=100)
    allowed_read_actions: list[ObservationReadAction] = Field(min_length=1, max_length=7)
    export_authorization_ref: InvestigationExactRef | None = None
    operator_ref: str = Field(min_length=1, max_length=200)
    human_assisted: bool
    issued_at: datetime
    expires_at: datetime
    status: ObservationSessionLeaseStatus
    idempotency_key: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=SHA256_PATTERN)
    created_by: str = Field(min_length=1, max_length=200)
    revoked_at: datetime | None = None
    revocation_reason: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("issued_at", "expires_at", "revoked_at")
    @classmethod
    def _aware_times(cls, value: datetime | None, info):
        return None if value is None else _aware(value, info.field_name)

    @field_validator("allowed_domains")
    @classmethod
    def _domains(cls, value: list[str]) -> list[str]:
        values = _unique(value, "allowedDomains")
        host = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
        if any(item != item.lower() or not host.fullmatch(item) for item in values):
            raise ValueError("allowed domain must be a lowercase host without scheme, port, path or query")
        return values

    @field_validator("allowed_route_patterns")
    @classmethod
    def _routes(cls, value: list[str]) -> list[str]:
        values = _unique(value, "allowedRoutePatterns")
        if any(
            not item.startswith("/")
            or "?" in item
            or "#" in item
            or ".." in item
            or "//" in item
            for item in values
        ):
            raise ValueError("allowed route must be a safe absolute semantic pattern without query or fragment")
        return values

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != OBSERVATION_SESSION_LEASE_SCHEMA_VERSION:
            raise ValueError("unsupported observation session lease schemaVersion")
        _require_type(self.channel_ref, "ChannelRevision", "channelRef")
        _require_type(self.entity_ref, "BusinessEntityRevision", "entityRef")
        _require_type(self.requirement_ref, "DataRequirementRevision", "requirementRef")
        _require_type(self.session_handle_ref, "ObservationSessionHandleRef", "sessionHandleRef")
        if self.revision != 1:
            raise ValueError("ObservationSessionLease issue revision must be 1")
        if self.expires_at <= self.issued_at:
            raise ValueError("expiresAt must be after issuedAt")
        if self.expires_at - self.issued_at > MAX_LEASE_DURATION:
            raise ValueError("observation lease must not exceed two hours")
        action_values = [action.value for action in self.allowed_read_actions]
        if len(action_values) != len(set(action_values)):
            raise ValueError("allowedReadActions must be unique")
        if ObservationReadAction.EXPORT in self.allowed_read_actions:
            if self.export_authorization_ref is None:
                raise ValueError("export action requires exact export authorization")
            _require_type(
                self.export_authorization_ref,
                "ReadOnlyExportAuthorizationRevision",
                "exportAuthorizationRef",
            )
        elif self.export_authorization_ref is not None:
            raise ValueError("export authorization is forbidden when export is not allowed")
        if self.status is ObservationSessionLeaseStatus.ACTIVE:
            if self.revoked_at is not None or self.revocation_reason is not None:
                raise ValueError("active lease cannot contain revocation fields")
        else:
            if self.revoked_at is None or self.revocation_reason is None:
                raise ValueError("revoked lease requires revokedAt and revocationReason")
            if self.revoked_at < self.issued_at:
                raise ValueError("revokedAt must not precede issuedAt")
        return self


class ObservationPageTarget(AipContractModel):
    domain: str
    route_pattern: str

    @field_validator("domain")
    @classmethod
    def _domain(cls, value: str) -> str:
        return ObservationSessionLeaseRecord._domains([value])[0]

    @field_validator("route_pattern")
    @classmethod
    def _route(cls, value: str) -> str:
        return ObservationSessionLeaseRecord._routes([value])[0]


class ObservationPlanStep(ObservationPageTarget):
    step_id: str = Field(min_length=1, max_length=120)
    action: ObservationReadAction
    expected_semantic_fields: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("expected_semantic_fields")
    @classmethod
    def _fields(cls, value: list[str]) -> list[str]:
        return _unique(value, "expectedSemanticFields")


class ObservationPaginationPolicy(AipContractModel):
    mode: Literal["none", "bounded"]
    max_pages: int = Field(ge=1, le=500)
    virtual_list: bool


class ObservationNetworkPolicy(AipContractModel):
    timeout_seconds: int = Field(ge=1, le=120)
    max_attempts: int = Field(ge=1, le=3)
    backoff_seconds: int = Field(ge=0, le=30)


class ObservationEvidencePolicy(AipContractModel):
    screenshot: bool
    dom: bool
    export: bool


REQUIRED_PROHIBITED_CONTROLS = frozenset(
    {
        "save", "submit", "delete", "list", "publish", "ship", "reprice",
        "contact", "sign", "settle", "batch", "permission-config",
    }
)


class ObservationPlanRevisionRecord(AipContractModel):
    schema_version: str = OBSERVATION_PLAN_SCHEMA_VERSION
    tenant: TenantContext
    plan_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    prior_ref: InvestigationExactRef | None = None
    content_hash: str = Field(pattern=SHA256_PATTERN)
    lease_ref: InvestigationExactRef
    requirement_ref: InvestigationExactRef
    goal: str = Field(min_length=1, max_length=1000)
    required_facts: list[str] = Field(min_length=1, max_length=100)
    page_inventory: list[ObservationPageTarget] = Field(min_length=1, max_length=100)
    steps: list[ObservationPlanStep] = Field(min_length=1, max_length=500)
    pagination_policy: ObservationPaginationPolicy
    network_policy: ObservationNetworkPolicy
    evidence_policy: ObservationEvidencePolicy
    prohibited_controls: list[str] = Field(min_length=1, max_length=100)
    stop_conditions: list[str] = Field(min_length=1, max_length=100)
    human_takeover_points: list[str] = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=SHA256_PATTERN)
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _created_at(cls, value: datetime) -> datetime:
        return _aware(value, "createdAt")

    @field_validator(
        "required_facts", "prohibited_controls", "stop_conditions", "human_takeover_points"
    )
    @classmethod
    def _unique_lists(cls, value: list[str], info) -> list[str]:
        return _unique(value, info.field_name)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != OBSERVATION_PLAN_SCHEMA_VERSION:
            raise ValueError("unsupported observation plan schemaVersion")
        _require_type(self.lease_ref, "ObservationSessionLeaseRevision", "leaseRef")
        _require_type(self.requirement_ref, "DataRequirementRevision", "requirementRef")
        if (self.revision == 1) != (self.prior_ref is None):
            raise ValueError("priorRef is absent only for revision 1")
        if self.prior_ref is not None:
            _require_type(self.prior_ref, "ObservationPlanRevision", "priorRef")
            if self.prior_ref.resource_id != self.plan_id or self.prior_ref.revision != self.revision - 1:
                raise ValueError("priorRef must target the preceding plan revision")
        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("stepId must be unique")
        if not REQUIRED_PROHIBITED_CONTROLS.issubset(self.prohibited_controls):
            raise ValueError("prohibitedControls must include the complete read-only denylist")
        if self.evidence_policy.export != any(step.action is ObservationReadAction.EXPORT for step in self.steps):
            raise ValueError("evidence export policy must match export steps")
        return self

    def validate_against_lease(self, lease: ObservationSessionLeaseRecord) -> None:
        if self.tenant != lease.tenant:
            raise ValueError("plan and lease tenant must match")
        if lease.status is not ObservationSessionLeaseStatus.ACTIVE:
            raise ValueError("plan requires an active lease")
        if self.lease_ref.resource_id != lease.lease_id or self.lease_ref.revision != lease.revision or self.lease_ref.content_hash != lease.content_hash:
            raise ValueError("plan leaseRef must exactly match lease authority")
        if self.requirement_ref != lease.requirement_ref:
            raise ValueError("plan requirementRef must equal lease requirementRef")
        if self.created_at >= lease.expires_at:
            raise ValueError("plan cannot be created after lease expiry")
        allowed_domains = set(lease.allowed_domains)
        allowed_routes = set(lease.allowed_route_patterns)
        allowed_actions = set(lease.allowed_read_actions)
        for target in [*self.page_inventory, *self.steps]:
            if target.domain not in allowed_domains:
                raise ValueError("plan domain is outside lease domain allowlist")
            if target.route_pattern not in allowed_routes:
                raise ValueError("plan route is outside lease route allowlist")
        for step in self.steps:
            if step.action not in allowed_actions:
                raise ValueError("plan action is outside lease action allowlist")
        if any(step.action is ObservationReadAction.EXPORT for step in self.steps) and lease.export_authorization_ref is None:
            raise ValueError("export step requires exact export authorization")


class ObservationReceiptStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class ObservationReceiptCoverage(AipContractModel):
    pages_expected: int = Field(ge=0)
    pages_observed: int = Field(ge=0)
    rows_expected: int = Field(ge=0)
    rows_observed: int = Field(ge=0)
    rows_unknown: int = Field(ge=0)

    @model_validator(mode="after")
    def _conserves_counts(self) -> Self:
        if self.pages_observed > self.pages_expected:
            raise ValueError("page coverage exceeds expected pages")
        if self.rows_observed + self.rows_unknown > self.rows_expected:
            raise ValueError("row coverage exceeds expected rows")
        return self


_LOCATION_EVIDENCE_TYPES = {
    "PageScreenshotArtifactRevision",
    "DOMSnapshotArtifactRevision",
    "ReadOnlyExportArtifactRevision",
}


class ObservationReceiptRecord(AipContractModel):
    schema_version: str = OBSERVATION_RECEIPT_SCHEMA_VERSION
    tenant: TenantContext
    receipt_id: str = Field(min_length=1, max_length=200)
    plan_ref: InvestigationExactRef
    step_ref: InvestigationExactRef
    capability_ref: InvestigationExactRef
    session_ref: InvestigationExactRef
    requirement_ref: InvestigationExactRef
    status: ObservationReceiptStatus
    semantic_route: str
    started_at: datetime
    cutoff_at: datetime
    finished_at: datetime
    observed_field_set: list[str] = Field(default_factory=list, max_length=100)
    coverage: ObservationReceiptCoverage
    location_evidence_refs: list[InvestigationExactRef] = Field(default_factory=list, max_length=100)
    fact_observation_refs: list[InvestigationExactRef] = Field(default_factory=list, max_length=100)
    page_fingerprint: str = Field(pattern=SHA256_PATTERN)
    operator_ref: str = Field(min_length=1, max_length=200)
    human_intervention: bool
    non_claims: list[str] = Field(min_length=1, max_length=100)
    next_step: str | None = Field(default=None, min_length=1, max_length=500)
    blockers: list[InvestigationBlocker] = Field(default_factory=list, max_length=50)
    content_hash: str = Field(pattern=SHA256_PATTERN)
    idempotency_key: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=SHA256_PATTERN)
    created_by: str = Field(min_length=1, max_length=200)

    @field_validator("started_at", "cutoff_at", "finished_at")
    @classmethod
    def _aware_receipt_times(cls, value: datetime, info) -> datetime:
        return _aware(value, info.field_name)

    @field_validator("semantic_route")
    @classmethod
    def _semantic_route(cls, value: str) -> str:
        try:
            return ObservationSessionLeaseRecord._routes([value])[0]
        except ValueError as exc:
            raise ValueError("semantic route must omit URL scheme, query and fragment") from exc

    @field_validator("observed_field_set", "non_claims")
    @classmethod
    def _receipt_lists(cls, value: list[str], info) -> list[str]:
        return _unique(value, info.field_name)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != OBSERVATION_RECEIPT_SCHEMA_VERSION:
            raise ValueError("unsupported observation receipt schemaVersion")
        _require_type(self.plan_ref, "ObservationPlanRevision", "planRef")
        _require_type(self.step_ref, "ObservationPlanStepRevision", "stepRef")
        _require_type(self.capability_ref, "CapabilityRevision", "capabilityRef")
        _require_type(self.session_ref, "ObservationSessionLeaseRevision", "sessionRef")
        _require_type(self.requirement_ref, "DataRequirementRevision", "requirementRef")
        if self.step_ref.revision != self.plan_ref.revision or self.step_ref.content_hash != self.plan_ref.content_hash:
            raise ValueError("stepRef must inherit exact plan revision and content hash")
        if not self.step_ref.resource_id.startswith(f"{self.plan_ref.resource_id}:"):
            raise ValueError("stepRef identity must be scoped by planId")
        if not (self.started_at <= self.cutoff_at <= self.finished_at):
            raise ValueError("receipt timestamp order must be startedAt <= cutoffAt <= finishedAt")
        keys: set[tuple[str, str, object, str]] = set()
        for ref in self.location_evidence_refs:
            if ref.resource_type not in _LOCATION_EVIDENCE_TYPES:
                raise ValueError("locationEvidenceRefs must contain only locating artifacts")
            key = (ref.resource_type, ref.resource_id, ref.revision, ref.content_hash)
            if key in keys:
                raise ValueError("locationEvidenceRefs must be unique")
            keys.add(key)
        keys.clear()
        for ref in self.fact_observation_refs:
            _require_type(ref, "PlatformObservation", "factObservationRefs")
            key = (ref.resource_type, ref.resource_id, ref.revision, ref.content_hash)
            if key in keys:
                raise ValueError("factObservationRefs must be unique")
            keys.add(key)
        if self.fact_observation_refs and not self.observed_field_set:
            raise ValueError("factObservationRefs require observedFieldSet")
        if self.status is ObservationReceiptStatus.SUCCEEDED:
            if self.blockers:
                raise ValueError("succeeded receipt cannot contain blockers")
            if not self.location_evidence_refs and not self.fact_observation_refs:
                raise ValueError("succeeded receipt requires locating evidence or fact observation")
        elif not self.blockers:
            raise ValueError("non-succeeded receipt requires an explicit blocker")
        return self
