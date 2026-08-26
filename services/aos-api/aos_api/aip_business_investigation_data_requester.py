"""BI-W5-04 missing-fact requester for canonical DataRequirement authority."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Protocol

from pydantic import Field, field_validator, model_validator

from aos_api.aip_business_investigation_runtime import (
    BusinessInvestigationRuntimeBinding,
)
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.business_investigation_shared_contracts import (
    DataRequirementStatus,
    InvestigationExactRef,
)
from aos_api.data_requirement_contracts import (
    DataRequirementRevisionRecord,
    DataRequirementTimeWindow,
)
from aos_api.data_requirement_store import (
    DataRequirementApplyResult,
    canonical_revision_content_hash,
)
from aos_api.tenant_scope import TenantScope


_FACT_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,119}$")


class MissingFactDataRequest(AipContractModel):
    requirement_id: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=1, max_length=200)
    purpose_code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,119}$")
    channel_ref: InvestigationExactRef
    entity_ref: InvestigationExactRef
    required_facts: list[str] = Field(min_length=1, max_length=100)
    time_window: DataRequirementTimeWindow
    grain: str = Field(pattern=r"^[a-z][a-z0-9_]{0,79}$")
    cutoff_at: datetime
    freshness_max_age_seconds: int = Field(ge=1, le=31_536_000)
    quality_threshold: float = Field(ge=0, le=1)
    markings: list[str] = Field(default_factory=list, max_length=50)
    min_population: int = Field(ge=1)
    acceptable_degradation: list[str] = Field(default_factory=list, max_length=50)
    requested_outputs: list[str] = Field(min_length=1, max_length=20)
    budget_minor: int = Field(ge=0)
    expires_at: datetime

    @field_validator("requirement_id", "idempotency_key")
    @classmethod
    def _trimmed(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("request identity must not be blank")
        return cleaned

    @field_validator("required_facts")
    @classmethod
    def _facts_are_safe_identifiers(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("requiredFacts must be unique")
        if any(not _FACT_PATTERN.fullmatch(item) for item in cleaned):
            raise ValueError("requiredFacts must contain bounded fact identifiers")
        return cleaned

    @field_validator("markings", "acceptable_degradation", "requested_outputs")
    @classmethod
    def _unique_non_blank(cls, value: list[str], info) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError(f"{info.field_name} must be unique and non-blank")
        return cleaned

    @field_validator("cutoff_at", "expires_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("request timestamps require timezone")
        return value

    @model_validator(mode="after")
    def _canonical_scope_refs_and_time(self) -> MissingFactDataRequest:
        if self.channel_ref.resource_type != "ChannelRevision":
            raise ValueError("channelRef must reference ChannelRevision")
        if self.entity_ref.resource_type != "BusinessEntityRevision":
            raise ValueError("entityRef must reference BusinessEntityRevision")
        if self.time_window.end_at > self.cutoff_at:
            raise ValueError("timeWindow must not extend beyond cutoffAt")
        return self


class BusinessInvestigationDataRequestBlocked(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class DataRequirementRequester(Protocol):
    def request(
        self,
        scope: TenantScope,
        actor: str,
        idempotency_key: str,
        item: DataRequirementRevisionRecord,
        *,
        expected_version: int,
    ) -> DataRequirementApplyResult: ...


class BusinessInvestigationDataRequester:
    """Request missing facts without reading or invoking any source system."""

    def __init__(self, requester: DataRequirementRequester) -> None:
        self._requester = requester

    def request_missing_facts(
        self,
        scope: TenantScope,
        runtime: BusinessInvestigationRuntimeBinding,
        request: MissingFactDataRequest,
        actor: str,
        *,
        created_at: datetime,
    ) -> DataRequirementApplyResult:
        tenant = TenantContext(org_id=scope.org_id, project_id=scope.project_id)
        if runtime.tenant != tenant:
            raise BusinessInvestigationDataRequestBlocked("RUNTIME_TENANT_MISMATCH")
        if runtime.checkpoint_ref is None:
            raise BusinessInvestigationDataRequestBlocked("CHECKPOINT_REQUIRED")
        if request.cutoff_at > created_at:
            raise BusinessInvestigationDataRequestBlocked("CUTOFF_AFTER_CREATED_AT")
        if request.expires_at <= created_at:
            raise BusinessInvestigationDataRequestBlocked("REQUIREMENT_ALREADY_EXPIRED")
        if not actor.strip():
            raise ValueError("actor is required")

        item = DataRequirementRevisionRecord(
            tenant=tenant,
            requirement_id=request.requirement_id,
            revision=1,
            prior_ref=None,
            content_hash=f"sha256:{'0' * 64}",
            status=DataRequirementStatus.REQUESTED,
            case_ref=self._exact_ref(runtime.case_ref),
            run_ref=self._exact_ref(runtime.business_investigation_run_ref),
            checkpoint_ref=InvestigationExactRef(
                resource_type="CheckpointRevision",
                resource_id=runtime.checkpoint_ref.resource_id,
                revision=runtime.checkpoint_ref.sequence,
                content_hash=f"sha256:{runtime.checkpoint_ref.state_hash}",
            ),
            purpose_code=request.purpose_code,
            channel_ref=request.channel_ref,
            entity_ref=request.entity_ref,
            required_facts=request.required_facts,
            time_window=request.time_window,
            grain=request.grain,
            cutoff_at=request.cutoff_at,
            freshness_max_age_seconds=request.freshness_max_age_seconds,
            quality_threshold=request.quality_threshold,
            markings=request.markings,
            pii_allowed=False,
            min_population=request.min_population,
            acceptable_degradation=request.acceptable_degradation,
            requested_outputs=request.requested_outputs,
            budget_minor=request.budget_minor,
            expires_at=request.expires_at,
            created_by=actor.strip(),
            created_at=created_at,
        )
        item = item.model_copy(
            update={"content_hash": canonical_revision_content_hash(item)}
        )
        return self._requester.request(
            scope,
            actor.strip(),
            request.idempotency_key,
            item,
            expected_version=0,
        )

    @staticmethod
    def _exact_ref(ref: ExactRevisionRef) -> InvestigationExactRef:
        return InvestigationExactRef(
            resource_type=ref.resource_type,
            resource_id=ref.resource_id,
            revision=ref.revision,
            content_hash=f"sha256:{ref.content_hash}",
        )
