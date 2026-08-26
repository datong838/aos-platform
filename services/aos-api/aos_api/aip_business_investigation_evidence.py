"""BI-W5-05 adapter for the canonical EvidenceBundle BuildJob."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Literal, Protocol

from pydantic import Field, field_validator, model_validator

from aos_api.aip_business_investigation_runtime import (
    BusinessInvestigationRuntimeBinding,
    CanonicalCheckpointRef,
)
from aos_api.aip_contracts import AipContractModel, ResourceRef, TenantContext
from aos_api.aip_production_contract_store import canonical_hash
from aos_api.aip_production_contracts import (
    BriefLifecycle,
    BuildEvidenceBundleRequest,
    Coverage,
    EvidenceBundleRevision,
    ExactRevisionRef,
    Freshness,
)
from aos_api.tenant_scope import TenantScope


_FACT_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,119}$")


class BusinessInvestigationEvidenceBuildRequest(AipContractModel):
    idempotency_key: str = Field(min_length=1, max_length=200)
    brief_ref: ExactRevisionRef
    subject_refs: list[ResourceRef] = Field(default_factory=list, max_length=100)
    required_fact_ids: list[str] = Field(min_length=1, max_length=100)
    supporting_evidence_refs: list[ExactRevisionRef] = Field(
        default_factory=list, max_length=200
    )
    counter_evidence_refs: list[ExactRevisionRef] = Field(
        default_factory=list, max_length=200
    )
    cutoff_at: datetime
    marking: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("idempotency_key")
    @classmethod
    def _trim_identity(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("idempotencyKey must not be blank")
        return cleaned

    @field_validator("required_fact_ids")
    @classmethod
    def _safe_unique_facts(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("requiredFactIds must be unique")
        if any(not _FACT_PATTERN.fullmatch(value) for value in cleaned):
            raise ValueError("requiredFactIds must contain bounded fact identifiers")
        return cleaned

    @field_validator("marking")
    @classmethod
    def _unique_markings(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("marking must be unique and non-blank")
        return cleaned

    @field_validator("cutoff_at")
    @classmethod
    def _aware_cutoff(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("cutoffAt requires timezone")
        return value

    @model_validator(mode="after")
    def _canonical_refs(self) -> BusinessInvestigationEvidenceBuildRequest:
        if self.brief_ref.resource_type != "TaskBriefRevision":
            raise ValueError("briefRef must reference TaskBriefRevision")
        combined = [*self.supporting_evidence_refs, *self.counter_evidence_refs]
        if not combined:
            raise ValueError("at least one canonical Evidence ref is required")
        if any(ref.resource_type != "Evidence" for ref in combined):
            raise ValueError("evidence refs must reference Evidence")
        identities = [ref.resource_id for ref in combined]
        if len(identities) != len(set(identities)):
            raise ValueError("supporting and counter Evidence refs must not overlap")
        return self

    @property
    def evidence_refs(self) -> list[ExactRevisionRef]:
        return [*self.supporting_evidence_refs, *self.counter_evidence_refs]


class BusinessInvestigationEvidenceAssessment(AipContractModel):
    required_fact_ids: list[str]
    covered_fact_ids: list[str]
    missing_fact_ids: list[str]
    required_count: int = Field(ge=1)
    covered_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    coverage: Coverage
    freshness: Freshness
    conflicts: list[dict[str, Any]]
    uncertainties: list[dict[str, Any]]
    counter_evidence_refs: list[ExactRevisionRef]


class BusinessInvestigationEvidenceBuildSideEffects(AipContractModel):
    provider_invocation_count: Literal[0] = 0
    source_read_count: Literal[0] = 0
    task_run_transition_count: Literal[0] = 0
    external_business_mutation_count: Literal[0] = 0


class BusinessInvestigationEvidenceBuildReceipt(AipContractModel):
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_binding_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    checkpoint_ref: CanonicalCheckpointRef
    evidence_bundle_ref: ExactRevisionRef
    side_effects: BusinessInvestigationEvidenceBuildSideEffects


class BusinessInvestigationEvidenceBuildResponse(AipContractModel):
    tenant: TenantContext
    bundle: EvidenceBundleRevision
    assessment: BusinessInvestigationEvidenceAssessment
    receipt: BusinessInvestigationEvidenceBuildReceipt


class BusinessInvestigationEvidenceBlocked(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class EvidenceBundleBuilder(Protocol):
    def build_evidence_bundle(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        body: BuildEvidenceBundleRequest,
    ) -> EvidenceBundleRevision: ...


class BusinessInvestigationEvidenceBuilder:
    """Delegate to canonical build authority and verify its exact result."""

    def __init__(self, builder: EvidenceBundleBuilder) -> None:
        self._builder = builder

    def build(
        self,
        scope: TenantScope,
        runtime: BusinessInvestigationRuntimeBinding,
        request: BusinessInvestigationEvidenceBuildRequest,
        actor: str,
        *,
        created_at: datetime,
    ) -> BusinessInvestigationEvidenceBuildResponse:
        tenant = TenantContext(org_id=scope.org_id, project_id=scope.project_id)
        if runtime.tenant != tenant:
            raise BusinessInvestigationEvidenceBlocked("RUNTIME_TENANT_MISMATCH")
        if runtime.checkpoint_ref is None:
            raise BusinessInvestigationEvidenceBlocked("CHECKPOINT_REQUIRED")
        if created_at.utcoffset() is None:
            raise ValueError("created_at requires timezone")
        if request.cutoff_at > created_at:
            raise BusinessInvestigationEvidenceBlocked("CUTOFF_AFTER_CREATED_AT")
        actor = actor.strip()
        if not actor:
            raise ValueError("actor is required")

        body = BuildEvidenceBundleRequest(
            brief_ref=request.brief_ref,
            subject_refs=request.subject_refs,
            cutoff_at=request.cutoff_at,
            item_refs=request.evidence_refs,
            required_fact_ids=request.required_fact_ids,
            marking=request.marking,
            license_summary={
                "status": "pending-policy-review",
                "authority": "business-investigation-evidence-adapter",
            },
        )
        bundle = self._builder.build_evidence_bundle(
            scope,
            actor,
            request.idempotency_key,
            body,
        )
        self._assert_exact_result(tenant, request, bundle)
        assessment = self._assessment(request, bundle)
        bundle_ref = ExactRevisionRef(
            resource_type="EvidenceBundleRevision",
            resource_id=bundle.bundle_id,
            revision=bundle.revision,
            content_hash=bundle.content_hash,
        )
        return BusinessInvestigationEvidenceBuildResponse(
            tenant=tenant,
            bundle=bundle,
            assessment=assessment,
            receipt=BusinessInvestigationEvidenceBuildReceipt(
                request_hash=canonical_hash(
                    request.model_dump(mode="json", by_alias=True)
                ),
                runtime_binding_hash=runtime.binding_hash,
                checkpoint_ref=runtime.checkpoint_ref,
                evidence_bundle_ref=bundle_ref,
                side_effects=BusinessInvestigationEvidenceBuildSideEffects(),
            ),
        )

    @staticmethod
    def _assert_exact_result(
        tenant: TenantContext,
        request: BusinessInvestigationEvidenceBuildRequest,
        bundle: EvidenceBundleRevision,
    ) -> None:
        if bundle.tenant != tenant:
            raise BusinessInvestigationEvidenceBlocked("BUNDLE_TENANT_DRIFTED")
        if bundle.brief_ref != request.brief_ref:
            raise BusinessInvestigationEvidenceBlocked("BUNDLE_BRIEF_DRIFTED")
        if bundle.subject_refs != request.subject_refs:
            raise BusinessInvestigationEvidenceBlocked("BUNDLE_SUBJECT_DRIFTED")
        if bundle.cutoff_at != request.cutoff_at:
            raise BusinessInvestigationEvidenceBlocked("BUNDLE_CUTOFF_DRIFTED")
        if bundle.item_refs != request.evidence_refs:
            raise BusinessInvestigationEvidenceBlocked("BUNDLE_EVIDENCE_DRIFTED")
        if bundle.marking != request.marking:
            raise BusinessInvestigationEvidenceBlocked("BUNDLE_MARKING_DRIFTED")
        if bundle.license_summary != {
            "status": "pending-policy-review",
            "authority": "business-investigation-evidence-adapter",
        }:
            raise BusinessInvestigationEvidenceBlocked("BUNDLE_LICENSE_DRIFTED")
        if bundle.lifecycle is not BriefLifecycle.FROZEN or bundle.revoked:
            raise BusinessInvestigationEvidenceBlocked("BUNDLE_NOT_ACTIVE_FROZEN")

    @staticmethod
    def _assessment(
        request: BusinessInvestigationEvidenceBuildRequest,
        bundle: EvidenceBundleRevision,
    ) -> BusinessInvestigationEvidenceAssessment:
        missing: list[str] = []
        for item in bundle.missing:
            fact_id = item.get("factId") if isinstance(item, dict) else None
            if not isinstance(fact_id, str) or fact_id not in request.required_fact_ids:
                raise BusinessInvestigationEvidenceBlocked("BUNDLE_MISSING_FACT_DRIFTED")
            missing.append(fact_id)
        if len(missing) != len(set(missing)):
            raise BusinessInvestigationEvidenceBlocked("BUNDLE_MISSING_FACT_DRIFTED")
        covered = [
            fact_id for fact_id in request.required_fact_ids if fact_id not in missing
        ]
        expected_coverage = (
            Coverage.COMPLETE
            if not missing
            else Coverage.BLOCKED
            if not covered
            else Coverage.PARTIAL
        )
        if bundle.coverage is not expected_coverage:
            raise BusinessInvestigationEvidenceBlocked("BUNDLE_COVERAGE_DRIFTED")
        for conflict in bundle.conflicts:
            fact_id = conflict.get("factId") if isinstance(conflict, dict) else None
            if fact_id not in request.required_fact_ids:
                raise BusinessInvestigationEvidenceBlocked("BUNDLE_CONFLICT_DRIFTED")
        return BusinessInvestigationEvidenceAssessment(
            required_fact_ids=request.required_fact_ids,
            covered_fact_ids=covered,
            missing_fact_ids=missing,
            required_count=len(request.required_fact_ids),
            covered_count=len(covered),
            missing_count=len(missing),
            coverage=bundle.coverage,
            freshness=bundle.freshness,
            conflicts=bundle.conflicts,
            uncertainties=bundle.uncertainties,
            counter_evidence_refs=request.counter_evidence_refs,
        )
