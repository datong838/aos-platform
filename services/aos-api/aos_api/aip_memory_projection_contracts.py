"""AIP-5 E7 contracts for agent-scoped memory projections and improvement facts.

The contracts are reference-only.  They never carry memory payloads, register
routes, allocate stores, or let a caller replace the Memory/Agent authorities.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import AipContractModel, ResourceRef, TenantContext
from aos_api.aip_eval_contracts import EvidenceQuality

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class MemoryProjectionKind(StrEnum):
    PERSONAL = "personal"
    SHARED = "shared"


class MemoryDisclosureMode(StrEnum):
    CITATION_ONLY = "citation_only"
    GOVERNED_SUMMARY = "governed_summary"


class MemoryProjectionStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"
    STALE = "stale"


class MemoryProjectionEventType(StrEnum):
    CREATED = "created"
    SUSPENDED = "suspended"
    REACTIVATED = "reactivated"
    REVOKED = "revoked"
    EXPIRED = "expired"
    STALED = "staled"


class ImprovementConclusion(StrEnum):
    IMPROVED = "improved"
    UNCHANGED = "unchanged"
    REGRESSED = "regressed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ImprovementMetricName(StrEnum):
    HUMAN_EDIT_RATE = "human_edit_rate"
    TASK_SUCCESS_RATE = "task_success_rate"
    CITATION_ACCEPTANCE_RATE = "citation_acceptance_rate"


def _validate_exact_agent_instance(ref: VersionedAssetRef) -> VersionedAssetRef:
    if ref.asset_type != "AgentInstance":
        raise ValueError("agent instance reference must use assetType=AgentInstance")
    return ref


def _validate_exact_resource(ref: ResourceRef, expected_type: str) -> ResourceRef:
    if ref.resource_type != expected_type or not ref.revision:
        raise ValueError(f"reference must be an exact {expected_type} revision")
    return ref


def _unique_non_blank(values: list[str], field_name: str) -> list[str]:
    cleaned = [value.strip() for value in values]
    if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
        raise ValueError(f"{field_name} must contain unique non-blank values")
    return cleaned


class MemoryRevisionExactRef(AipContractModel):
    memory_item_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=SHA256_PATTERN)

    @field_validator("memory_item_id")
    @classmethod
    def _memory_id_non_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("memory_item_id must not be blank")
        return cleaned


class MemoryProjectionExactRef(AipContractModel):
    projection_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)
    content_hash: str = Field(pattern=SHA256_PATTERN)


class CreateMemoryProjectionRequest(AipContractModel):
    projection_id: str = Field(min_length=1, max_length=200)
    kind: MemoryProjectionKind
    owner_instance_ref: VersionedAssetRef
    memory_ref: MemoryRevisionExactRef
    recipient_instance_refs: list[VersionedAssetRef] = Field(
        default_factory=list, max_length=128
    )
    allowed_purposes: list[str] = Field(min_length=1, max_length=64)
    allowed_markings: list[str] = Field(min_length=1, max_length=32)
    disclosure: MemoryDisclosureMode = MemoryDisclosureMode.CITATION_ONLY
    effective_at: datetime
    expires_at: datetime

    @field_validator("projection_id")
    @classmethod
    def _projection_id_non_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("projection_id must not be blank")
        return cleaned

    @field_validator("owner_instance_ref")
    @classmethod
    def _owner_is_instance(cls, value: VersionedAssetRef) -> VersionedAssetRef:
        return _validate_exact_agent_instance(value)

    @field_validator("recipient_instance_refs")
    @classmethod
    def _recipients_are_exact_instances(
        cls, values: list[VersionedAssetRef]
    ) -> list[VersionedAssetRef]:
        for value in values:
            _validate_exact_agent_instance(value)
        identities = [
            (value.asset_id, value.revision, value.content_hash) for value in values
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("recipient instance refs must be unique")
        return values

    @field_validator("allowed_purposes", "allowed_markings")
    @classmethod
    def _allowlists_are_unique(cls, values: list[str], info) -> list[str]:
        return _unique_non_blank(values, info.field_name)

    @model_validator(mode="after")
    def _projection_invariants(self) -> CreateMemoryProjectionRequest:
        recipients = self.recipient_instance_refs
        if self.kind is MemoryProjectionKind.PERSONAL and recipients:
            raise ValueError("personal projection must not have recipients")
        if self.kind is MemoryProjectionKind.SHARED and not recipients:
            raise ValueError("shared projection requires explicit recipients")
        if any(
            recipient.asset_id == self.owner_instance_ref.asset_id
            for recipient in recipients
        ):
            raise ValueError("projection owner cannot also be a recipient")
        if self.expires_at <= self.effective_at:
            raise ValueError("expires_at must follow effective_at")
        return self


class ChangeMemoryProjectionStatusRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    from_status: MemoryProjectionStatus
    to_status: MemoryProjectionStatus
    reason_hash: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _allowed_transition(self) -> ChangeMemoryProjectionStatusRequest:
        allowed = {
            (MemoryProjectionStatus.ACTIVE, MemoryProjectionStatus.SUSPENDED),
            (MemoryProjectionStatus.SUSPENDED, MemoryProjectionStatus.ACTIVE),
            (MemoryProjectionStatus.ACTIVE, MemoryProjectionStatus.REVOKED),
            (MemoryProjectionStatus.SUSPENDED, MemoryProjectionStatus.REVOKED),
        }
        if (self.from_status, self.to_status) not in allowed:
            raise ValueError("projection status transition is not caller-authorized")
        return self


class MemoryProjection(AipContractModel):
    tenant: TenantContext
    projection_ref: MemoryProjectionExactRef
    kind: MemoryProjectionKind
    owner_instance_ref: VersionedAssetRef
    memory_ref: MemoryRevisionExactRef
    recipient_instance_refs: list[VersionedAssetRef] = Field(max_length=128)
    allowed_purposes: list[str] = Field(min_length=1, max_length=64)
    allowed_markings: list[str] = Field(min_length=1, max_length=32)
    disclosure: MemoryDisclosureMode
    status: MemoryProjectionStatus
    effective_at: datetime
    expires_at: datetime
    created_by: str = Field(min_length=1, max_length=320)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _response_invariants(self) -> MemoryProjection:
        CreateMemoryProjectionRequest(
            projection_id=self.projection_ref.projection_id,
            kind=self.kind,
            owner_instance_ref=self.owner_instance_ref,
            memory_ref=self.memory_ref,
            recipient_instance_refs=self.recipient_instance_refs,
            allowed_purposes=self.allowed_purposes,
            allowed_markings=self.allowed_markings,
            disclosure=self.disclosure,
            effective_at=self.effective_at,
            expires_at=self.expires_at,
        )
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        return self


class MemoryProjectionEvent(AipContractModel):
    tenant: TenantContext
    event_id: str = Field(min_length=1, max_length=200)
    projection_ref: MemoryProjectionExactRef
    sequence: int = Field(ge=1)
    event_type: MemoryProjectionEventType
    from_status: MemoryProjectionStatus | None = None
    to_status: MemoryProjectionStatus
    reason_hash: str = Field(pattern=SHA256_PATTERN)
    event_hash: str = Field(pattern=SHA256_PATTERN)
    actor: str = Field(min_length=1, max_length=320)
    occurred_at: datetime

    @model_validator(mode="after")
    def _event_status_matches(self) -> MemoryProjectionEvent:
        expected = {
            MemoryProjectionEventType.CREATED: MemoryProjectionStatus.ACTIVE,
            MemoryProjectionEventType.SUSPENDED: MemoryProjectionStatus.SUSPENDED,
            MemoryProjectionEventType.REACTIVATED: MemoryProjectionStatus.ACTIVE,
            MemoryProjectionEventType.REVOKED: MemoryProjectionStatus.REVOKED,
            MemoryProjectionEventType.EXPIRED: MemoryProjectionStatus.EXPIRED,
            MemoryProjectionEventType.STALED: MemoryProjectionStatus.STALE,
        }[self.event_type]
        if self.to_status is not expected:
            raise ValueError("projection event type must match target status")
        if self.event_type is MemoryProjectionEventType.CREATED:
            if self.sequence != 1 or self.from_status is not None:
                raise ValueError("created event must be the initial event")
        elif self.from_status is None:
            raise ValueError("non-created projection event requires from_status")
        return self


class MemoryProjectionReceipt(AipContractModel):
    tenant: TenantContext
    receipt_id: str = Field(min_length=1, max_length=200)
    operation: str = Field(
        pattern=r"^(create|suspend|reactivate|revoke)$", max_length=40
    )
    idempotency_key: str = Field(min_length=1, max_length=240)
    request_hash: str = Field(pattern=SHA256_PATTERN)
    result_ref: MemoryProjectionExactRef
    actor: str = Field(min_length=1, max_length=320)
    created_at: datetime


class MemoryExposure(AipContractModel):
    tenant: TenantContext
    exposure_id: str = Field(min_length=1, max_length=200)
    agent_run_ref: ResourceRef
    task_run_ref: ResourceRef
    agent_instance_ref: VersionedAssetRef
    skill_ref: VersionedAssetRef
    logic_ref: VersionedAssetRef
    projection_ref: MemoryProjectionExactRef
    memory_ref: MemoryRevisionExactRef
    eval_contract_ref: VersionedAssetRef
    time_cutoff: datetime
    accepted_at: datetime
    exposure_hash: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _exact_runtime_context(self) -> MemoryExposure:
        _validate_exact_resource(self.agent_run_ref, "AgentRun")
        _validate_exact_resource(self.task_run_ref, "TaskRun")
        _validate_exact_agent_instance(self.agent_instance_ref)
        if self.skill_ref.asset_type != "SkillTemplate":
            raise ValueError("skill_ref must reference SkillTemplate")
        if self.logic_ref.asset_type != "LogicRevision":
            raise ValueError("logic_ref must reference LogicRevision")
        if self.eval_contract_ref.asset_type != "EvalContract":
            raise ValueError("eval_contract_ref must reference EvalContract")
        if self.accepted_at < self.time_cutoff:
            raise ValueError("accepted_at must not precede time_cutoff")
        return self


class ImprovementMetric(AipContractModel):
    metric_name: ImprovementMetricName
    baseline_value: float = Field(ge=0.0, le=1.0)
    treatment_value: float = Field(ge=0.0, le=1.0)
    baseline_sample_size: int = Field(ge=1)
    treatment_sample_size: int = Field(ge=1)
    confidence_interval_lower: float | None = Field(default=None, ge=-1.0, le=1.0)
    confidence_interval_upper: float | None = Field(default=None, ge=-1.0, le=1.0)

    @model_validator(mode="after")
    def _confidence_interval(self) -> ImprovementMetric:
        bounds = (self.confidence_interval_lower, self.confidence_interval_upper)
        if (bounds[0] is None) != (bounds[1] is None):
            raise ValueError("confidence interval bounds must be provided together")
        if bounds[0] is not None and bounds[0] > bounds[1]:
            raise ValueError("confidence interval lower bound must not exceed upper")
        return self


class ImprovementObservation(AipContractModel):
    tenant: TenantContext
    observation_id: str = Field(min_length=1, max_length=200)
    agent_instance_ref: VersionedAssetRef
    metric_definition_ref: VersionedAssetRef
    eval_contract_ref: VersionedAssetRef
    eval_report_ref: VersionedAssetRef | None = None
    baseline_cohort_ref: VersionedAssetRef | None = None
    treatment_cohort_ref: VersionedAssetRef | None = None
    exposure_refs: list[VersionedAssetRef] = Field(default_factory=list, max_length=10000)
    metrics: list[ImprovementMetric] = Field(default_factory=list, max_length=3)
    quality: EvidenceQuality
    source_refs: list[VersionedAssetRef] = Field(default_factory=list, max_length=128)
    cutoff_at: datetime
    observed_at: datetime
    conclusion: ImprovementConclusion
    limitations: list[str] = Field(default_factory=list, max_length=64)
    observation_hash: str = Field(pattern=SHA256_PATTERN)

    @field_validator("agent_instance_ref")
    @classmethod
    def _observation_instance(cls, value: VersionedAssetRef) -> VersionedAssetRef:
        return _validate_exact_agent_instance(value)

    @field_validator("source_refs", "exposure_refs")
    @classmethod
    def _exact_unique_assets(
        cls, values: list[VersionedAssetRef], info
    ) -> list[VersionedAssetRef]:
        identities = [
            (value.asset_type, value.asset_id, value.revision, value.content_hash)
            for value in values
        ]
        if len(identities) != len(set(identities)):
            raise ValueError(f"{info.field_name} must be unique")
        if info.field_name == "exposure_refs":
            if any(value.asset_type != "MemoryExposure" for value in values):
                raise ValueError("exposure_refs must reference MemoryExposure")
        elif any(
            value.asset_type
            not in {"EvalReport", "EvidenceSnapshot", "MetricSnapshot"}
            for value in values
        ):
            raise ValueError("source_refs must reference governed evidence assets")
        return values

    @field_validator("metrics")
    @classmethod
    def _unique_metrics(cls, values: list[ImprovementMetric]) -> list[ImprovementMetric]:
        names = [value.metric_name for value in values]
        if len(names) != len(set(names)):
            raise ValueError("improvement metric names must be unique")
        return values

    @field_validator("limitations")
    @classmethod
    def _unique_limitations(cls, values: list[str]) -> list[str]:
        return _unique_non_blank(values, "limitations")

    @model_validator(mode="after")
    def _evidence_quality(self) -> ImprovementObservation:
        if self.metric_definition_ref.asset_type != "MetricDefinition":
            raise ValueError("metric_definition_ref must reference MetricDefinition")
        if self.eval_contract_ref.asset_type != "EvalContract":
            raise ValueError("eval_contract_ref must reference EvalContract")
        if self.observed_at < self.cutoff_at:
            raise ValueError("observed_at must not precede cutoff_at")

        comparable_refs = (
            self.eval_report_ref,
            self.baseline_cohort_ref,
            self.treatment_cohort_ref,
        )
        if self.quality is EvidenceQuality.UNKNOWN:
            if self.metrics or self.source_refs or any(comparable_refs):
                raise ValueError("unknown improvement must not invent metrics or sources")
            if self.conclusion is not ImprovementConclusion.INSUFFICIENT_EVIDENCE:
                raise ValueError("unknown improvement requires insufficient_evidence")
            return self

        if not self.metrics or not self.source_refs or not self.exposure_refs:
            raise ValueError(
                "measured or estimated improvement requires metrics, sources and exposures"
            )
        if any(value is None for value in comparable_refs):
            raise ValueError(
                "measured or estimated improvement requires exact eval and cohort refs"
            )
        expected_types = {
            "eval_report_ref": "EvalReport",
            "baseline_cohort_ref": "CohortSnapshot",
            "treatment_cohort_ref": "CohortSnapshot",
        }
        for field_name, expected_type in expected_types.items():
            if getattr(self, field_name).asset_type != expected_type:
                raise ValueError(f"{field_name} must reference {expected_type}")
        if self.conclusion is ImprovementConclusion.INSUFFICIENT_EVIDENCE:
            if not self.limitations:
                raise ValueError("insufficient evidence requires limitations")
        return self
