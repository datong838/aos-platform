"""W4-01 early bridge from canonical preparation to EvidenceBundle."""
from __future__ import annotations

from typing import Literal, Protocol

from pydantic import Field

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_production_contract_store import (
    AipProductionContractStore,
    ProductionContractDependencyBlocked,
    ProductionContractError,
    canonical_hash,
)
from aos_api.aip_production_contracts import (
    BriefLifecycle,
    BuildEvidenceBundleRequest,
    EvidenceBundleRevision,
    ExactRevisionRef,
    TaskBriefRevision,
)
from aos_api.aip_production_profile_contracts import ProductionProfile
from aos_api.aip_responsibility_template_authority import (
    InstalledProductionProfileResolver,
)
from aos_api.ecommerce_workshop_prepare_contracts import (
    EcommerceWorkshopPrepareResponse,
)
from aos_api.ecommerce_workshop_prepare_store import (
    EcommerceWorkshopPrepareStore,
    PreparationStoreError,
)
from aos_api.tenant_scope import TenantScope


class WorkshopEvidenceBuildRequest(AipContractModel):
    command: Literal["build-evidence"] = "build-evidence"
    preparation_id: str = Field(min_length=1, max_length=200)
    production_profile_ref: ExactRevisionRef


class WorkshopEvidenceBuildSideEffects(AipContractModel):
    provider_invocation_count: Literal[0] = 0
    provider_fee: Literal[0] = 0
    task_run_created_count: Literal[0] = 0
    agent_run_created_count: Literal[0] = 0
    action_or_handoff_created_count: Literal[0] = 0
    approval_or_execution_lease_created_count: Literal[0] = 0
    external_business_mutation_count: Literal[0] = 0


class WorkshopEvidenceBuildReceipt(AipContractModel):
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    preparation_id: str
    frozen_brief_ref: ExactRevisionRef
    evidence_bundle_ref: ExactRevisionRef
    side_effects: WorkshopEvidenceBuildSideEffects
    next_allowed_commands: list[str] = Field(default_factory=list)


class WorkshopEvidenceBuildResponse(AipContractModel):
    tenant: TenantContext
    module_id: str
    production_profile_ref: ExactRevisionRef
    bundle: EvidenceBundleRevision
    receipt: WorkshopEvidenceBuildReceipt


class WorkshopEvidenceBuildError(RuntimeError):
    code = "WORKSHOP_EVIDENCE_BUILD_ERROR"


class WorkshopEvidenceBuildBlocked(WorkshopEvidenceBuildError):
    code = "WORKSHOP_EVIDENCE_BUILD_BLOCKED"


class WorkshopEvidenceBuildUnavailable(WorkshopEvidenceBuildError):
    code = "WORKSHOP_EVIDENCE_BUILD_UNAVAILABLE"


class ProfileReader(Protocol):
    def __call__(
        self, scope: TenantScope, ref: ExactRevisionRef
    ) -> ProductionProfile | None: ...


class ProductionAuthority(Protocol):
    def get_brief(
        self, scope: TenantScope, brief_id: str, revision: int | None = None
    ) -> TaskBriefRevision: ...

    def freeze_brief(
        self,
        scope: TenantScope,
        actor: str,
        brief_id: str,
        expected_version: int,
        key: str,
    ) -> TaskBriefRevision: ...

    def build_evidence_bundle(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        body: BuildEvidenceBundleRequest,
    ) -> EvidenceBundleRevision: ...


class EcommerceWorkshopEvidenceBuildService:
    def __init__(
        self,
        *,
        preparation_store: EcommerceWorkshopPrepareStore | None = None,
        production_authority: ProductionAuthority | None = None,
        profile_reader: ProfileReader | None = None,
    ) -> None:
        self._preparations = preparation_store or EcommerceWorkshopPrepareStore()
        self._production = production_authority or AipProductionContractStore()
        resolver = InstalledProductionProfileResolver()
        self._profile_reader = profile_reader or resolver.load_profile

    def build(
        self,
        scope: TenantScope,
        *,
        actor: str,
        module_id: str,
        idempotency_key: str,
        body: WorkshopEvidenceBuildRequest,
    ) -> WorkshopEvidenceBuildResponse:
        try:
            record = self._preparations.get(scope, body.preparation_id)
        except PreparationStoreError as exc:
            raise WorkshopEvidenceBuildUnavailable(str(exc)) from exc
        if record.status != "complete" or record.result_body is None:
            raise WorkshopEvidenceBuildBlocked("preparation is not complete")
        prepared = EcommerceWorkshopPrepareResponse.model_validate(record.result_body)
        if prepared.module_id != module_id:
            raise WorkshopEvidenceBuildBlocked("preparation belongs to another module")
        if prepared.evidence_build_request.production_profile_ref != body.production_profile_ref:
            raise WorkshopEvidenceBuildBlocked("production profile exact ref drifted")
        profile = self._profile_reader(scope, body.production_profile_ref)
        if profile is None or profile.module_id != module_id:
            raise WorkshopEvidenceBuildBlocked(
                "installed production profile is missing, drifted, or belongs to another module"
            )
        required_facts = list(profile.evidence_selection.required_facts)
        if prepared.evidence_build_request.required_fact_ids != required_facts:
            raise WorkshopEvidenceBuildBlocked("required facts drifted from installed profile")
        evidence_refs = list(prepared.evidence_build_request.canonical_evidence_refs)
        if not evidence_refs:
            raise WorkshopEvidenceBuildBlocked("canonical Evidence refs are required")

        prepared_brief = prepared.draft_brief_ref
        try:
            current = self._production.get_brief(scope, prepared_brief.resource_id)
            if current.content_hash != prepared_brief.content_hash:
                raise WorkshopEvidenceBuildBlocked("prepared Brief content drifted")
            if current.lifecycle is BriefLifecycle.DRAFT:
                if current.revision != prepared_brief.revision:
                    raise WorkshopEvidenceBuildBlocked("prepared Brief revision is not current")
                current = self._production.freeze_brief(
                    scope,
                    actor,
                    current.brief_id,
                    current.version,
                    f"{idempotency_key}:brief:freeze",
                )
            elif current.lifecycle is not BriefLifecycle.FROZEN:
                raise WorkshopEvidenceBuildBlocked("prepared Brief cannot be frozen")
            frozen_ref = ExactRevisionRef(
                resource_type="TaskBriefRevision",
                resource_id=current.brief_id,
                revision=current.revision,
                content_hash=current.content_hash,
            )
            bundle = self._production.build_evidence_bundle(
                scope,
                actor,
                f"{idempotency_key}:bundle:build",
                BuildEvidenceBundleRequest(
                    brief_ref=frozen_ref,
                    subject_refs=prepared.evidence_build_request.subject_refs,
                    cutoff_at=prepared.evidence_build_request.cutoff_at,
                    item_refs=evidence_refs,
                    required_fact_ids=required_facts,
                    marking=prepared.evidence_build_request.marking,
                    license_summary={
                        "status": "pending-policy-review",
                        "authority": "installed-production-profile",
                    },
                ),
            )
        except WorkshopEvidenceBuildError:
            raise
        except ProductionContractDependencyBlocked as exc:
            raise WorkshopEvidenceBuildBlocked(str(exc)) from exc
        except ProductionContractError as exc:
            raise WorkshopEvidenceBuildUnavailable(str(exc)) from exc

        bundle_ref = ExactRevisionRef(
            resource_type="EvidenceBundleRevision",
            resource_id=bundle.bundle_id,
            revision=bundle.revision,
            content_hash=bundle.content_hash,
        )
        request_hash = canonical_hash(
            {
                "moduleId": module_id,
                **body.model_dump(mode="json", by_alias=True),
            }
        )
        return WorkshopEvidenceBuildResponse(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            module_id=module_id,
            production_profile_ref=body.production_profile_ref,
            bundle=bundle,
            receipt=WorkshopEvidenceBuildReceipt(
                request_hash=request_hash,
                preparation_id=body.preparation_id,
                frozen_brief_ref=frozen_ref,
                evidence_bundle_ref=bundle_ref,
                side_effects=WorkshopEvidenceBuildSideEffects(),
            ),
        )
