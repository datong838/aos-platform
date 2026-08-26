"""BI-W5-03 adapter from investigation steps to canonical ResearchJob."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Literal, Protocol

from pydantic import Field, field_validator, model_validator

from aos_api.aip_business_investigation_runtime import (
    BusinessInvestigationRuntimeBinding,
)
from aos_api.aip_contracts import AipContractModel, ResourceRef, TenantContext
from aos_api.aip_research_job import (
    CreateResearchJobRequest,
    ResearchJobManifest,
    ResearchJobSnapshot,
    canonical_research_manifest_hash,
)
from aos_api.tenant_scope import TenantScope


ResearchKind = Literal["data", "ontology", "human"]
_FORBIDDEN_REF_PARTS = ("secret", "credential", "cookie", "token", "password")


class InvestigationResearchBudget(AipContractModel):
    max_tokens: int = Field(default=0, ge=0, le=10_000_000)
    max_cost_micros: int = Field(default=0, ge=0, le=10_000_000_000)
    max_duration_seconds: int = Field(default=300, ge=1, le=86_400)


class InvestigationResearchRoute(AipContractModel):
    research_kind: ResearchKind
    provider_id: str = Field(min_length=1, max_length=160)
    provider_revision: int = Field(ge=1)
    source_authority: str = Field(min_length=1, max_length=160)
    allowed_source_resource_types: list[str] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def _source_types_are_stable(self) -> InvestigationResearchRoute:
        values = [value.strip() for value in self.allowed_source_resource_types]
        if any(not value for value in values) or len(values) != len(set(values)):
            raise ValueError("allowedSourceResourceTypes must be unique and non-blank")
        self.allowed_source_resource_types = values
        return self


class InvestigationResearchStepRequest(AipContractModel):
    research_kind: ResearchKind
    step_key: str = Field(min_length=1, max_length=200)
    source_owner_ref: ResourceRef
    input_refs: list[ResourceRef] = Field(default_factory=list, max_length=128)
    lineage_ref: ResourceRef
    output_schema_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    budget: InvestigationResearchBudget = Field(
        default_factory=InvestigationResearchBudget
    )
    traceparent: str = Field(
        pattern=r"^00-[0-9a-f]{32}-[0-9a-f]{16}-(?:00|01)$"
    )
    deadline: datetime
    idempotency_key: str = Field(min_length=1, max_length=160)

    @field_validator("step_key", "idempotency_key")
    @classmethod
    def _trimmed(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("research step fields must not be blank")
        return cleaned

    @model_validator(mode="after")
    def _refs_remain_external_authorities(self) -> InvestigationResearchStepRequest:
        refs = [self.source_owner_ref, *self.input_refs]
        identities = []
        for ref in refs:
            if not ref.revision:
                raise ValueError("research scoped refs require exact revision")
            lowered = f"{ref.resource_type}:{ref.authority}".lower()
            if any(part in lowered for part in _FORBIDDEN_REF_PARTS):
                raise ValueError("research scoped refs cannot reference secret material")
            identity = (
                ref.resource_type,
                ref.resource_id,
                ref.revision,
                ref.authority,
            )
            if identity in identities:
                raise ValueError("research scoped refs must be unique")
            identities.append(identity)
        lineage = self.lineage_ref
        try:
            sequence = int(lineage.revision or "")
        except ValueError as exc:
            raise ValueError("lineageRef requires a positive exact sequence") from exc
        if (
            lineage.resource_type != "aip.lineage"
            or lineage.authority != "aos.lineage"
            or sequence < 1
        ):
            raise ValueError("lineageRef must reference exact aos.lineage authority")
        if self.deadline.tzinfo is None:
            raise ValueError("research deadline requires timezone")
        return self


class BusinessInvestigationResearchBlocked(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ResearchRouteResolver(Protocol):
    def __call__(
        self, scope: TenantScope, research_kind: ResearchKind
    ) -> InvestigationResearchRoute: ...


class ResearchJobCreator(Protocol):
    def create_job(
        self,
        scope: TenantScope,
        request: CreateResearchJobRequest,
        actor: str,
        *,
        now: datetime | None = None,
    ) -> ResearchJobSnapshot: ...


class BusinessInvestigationResearchAdapter:
    """Create only a canonical ResearchJob manifest; never execute a provider."""

    def __init__(
        self,
        route_resolver: ResearchRouteResolver,
        job_creator: ResearchJobCreator,
    ) -> None:
        self._route_resolver = route_resolver
        self._job_creator = job_creator

    def create_job(
        self,
        scope: TenantScope,
        runtime: BusinessInvestigationRuntimeBinding,
        request: InvestigationResearchStepRequest,
        actor: str,
        *,
        now: datetime,
    ) -> ResearchJobSnapshot:
        tenant = TenantContext(org_id=scope.org_id, project_id=scope.project_id)
        if runtime.tenant != tenant:
            raise BusinessInvestigationResearchBlocked("RUNTIME_TENANT_MISMATCH")
        if request.deadline <= now:
            raise BusinessInvestigationResearchBlocked("RESEARCH_DEADLINE_EXPIRED")
        try:
            route = self._route_resolver(scope, request.research_kind)
        except Exception as exc:
            raise BusinessInvestigationResearchBlocked(
                "RESEARCH_ROUTE_RESOLUTION_FAILED"
            ) from exc
        if route.research_kind != request.research_kind:
            raise BusinessInvestigationResearchBlocked("RESEARCH_ROUTE_KIND_DRIFTED")
        owner = request.source_owner_ref
        if owner.authority != route.source_authority:
            raise BusinessInvestigationResearchBlocked("SOURCE_OWNER_AUTHORITY_DRIFTED")
        if owner.resource_type not in route.allowed_source_resource_types:
            raise BusinessInvestigationResearchBlocked("SOURCE_OWNER_TYPE_BLOCKED")
        if not actor.strip():
            raise ValueError("actor is required")

        task_run_ref = ResourceRef(
            resource_type="aos.task_run",
            resource_id=runtime.task_run_ref.resource_id,
            revision=str(runtime.task_run_ref.version),
            authority="aos.task",
        )
        scoped_refs = [owner, *request.input_refs]
        manifest = ResearchJobManifest(
            task_run_ref=task_run_ref,
            lineage_ref=request.lineage_ref,
            provider=route.provider_id,
            binding_revision=str(route.provider_revision),
            manifest_hash="0" * 64,
            idempotency_key=request.idempotency_key,
            budget={
                **request.budget.model_dump(mode="json", by_alias=True),
                "researchKind": request.research_kind,
            },
            scoped_refs=scoped_refs,
            output_schema_hash=request.output_schema_hash,
            traceparent=request.traceparent,
            deadline=request.deadline,
        )
        manifest = manifest.model_copy(
            update={"manifest_hash": canonical_research_manifest_hash(manifest)}
        )
        return self._job_creator.create_job(
            scope,
            CreateResearchJobRequest(
                run_id=runtime.task_run_ref.resource_id,
                step_key=request.step_key,
                provider_id=route.provider_id,
                provider_revision=route.provider_revision,
                manifest=manifest,
            ),
            actor.strip(),
            now=now,
        )
