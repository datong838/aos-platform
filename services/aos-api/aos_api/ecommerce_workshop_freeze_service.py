"""W3-04 Workshop adapter over the canonical ProductionContext authority."""
from __future__ import annotations

from typing import Protocol

from aos_api.aip_contracts import TenantContext
from aos_api.aip_production_contract_store import (
    AipProductionContractStore,
    ProductionContractConflict,
    ProductionContractDependencyBlocked,
    ProductionContractError,
    canonical_hash,
)
from aos_api.aip_production_contracts import (
    EvalContractRevision,
    EvidenceBundleRevision,
    ExactRevisionRef,
    FreezeProductionContextRequest,
    ProductionContextRevision,
    ResponsibilityPlanRevision,
    TaskBriefRevision,
)
from aos_api.aip_production_profile_contracts import ProductionProfile
from aos_api.aip_responsibility_template_authority import InstalledProductionProfileResolver
from aos_api.ecommerce_workshop_freeze_contracts import (
    WorkshopFreezeReceipt,
    WorkshopFreezeRequest,
    WorkshopFreezeResponse,
)
from aos_api.ecommerce_workshop_prepare_contracts import (
    EcommerceWorkshopPrepareResponse,
    PrepareSideEffectCounters,
)
from aos_api.ecommerce_workshop_prepare_store import (
    EcommerceWorkshopPrepareStore,
    PreparationStoreError,
)
from aos_api.tenant_scope import TenantScope


class WorkshopFreezeError(RuntimeError):
    code = "WORKSHOP_FREEZE_ERROR"


class WorkshopFreezeBlocked(WorkshopFreezeError):
    code = "WORKSHOP_FREEZE_BLOCKED"


class WorkshopFreezeConflict(WorkshopFreezeError):
    code = "WORKSHOP_FREEZE_CONFLICT"


class WorkshopFreezeUnavailable(WorkshopFreezeError):
    code = "WORKSHOP_FREEZE_UNAVAILABLE"


class ProfileReader(Protocol):
    def __call__(self, scope: TenantScope, ref: ExactRevisionRef) -> ProductionProfile | None: ...


class ProductionAuthority(Protocol):
    def get_brief(
        self, scope: TenantScope, brief_id: str, revision: int | None = None
    ) -> TaskBriefRevision: ...

    def get_evidence_bundle(
        self, scope: TenantScope, bundle_id: str, revision: int = 1
    ) -> EvidenceBundleRevision: ...

    def get_eval_contract(
        self, scope: TenantScope, contract_id: str, revision: int | None = None
    ) -> EvalContractRevision: ...

    def get_responsibility_plan(
        self, scope: TenantScope, plan_id: str, revision: int | None = None
    ) -> ResponsibilityPlanRevision: ...

    def freeze_production_context(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        body: FreezeProductionContextRequest,
    ) -> ProductionContextRevision: ...


class EcommerceWorkshopFreezeService:
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

    def freeze(
        self,
        scope: TenantScope,
        *,
        actor: str,
        module_id: str,
        idempotency_key: str,
        body: WorkshopFreezeRequest,
    ) -> WorkshopFreezeResponse:
        try:
            record = self._preparations.get(scope, body.preparation_id)
        except PreparationStoreError as exc:
            raise WorkshopFreezeUnavailable(str(exc)) from exc
        if record.status != "complete" or record.result_body is None:
            raise WorkshopFreezeBlocked("preparation is not complete")
        prepared = EcommerceWorkshopPrepareResponse.model_validate(record.result_body)
        if prepared.tenant.org_id != scope.org_id or prepared.tenant.project_id != scope.project_id:
            raise WorkshopFreezeBlocked("preparation tenant scope drifted")
        if prepared.module_id != module_id or record.module_id != module_id:
            raise WorkshopFreezeBlocked("preparation belongs to another module")
        if prepared.evidence_build_request.production_profile_ref != body.production_profile_ref:
            raise WorkshopFreezeBlocked("production profile exact ref drifted")
        profile = self._profile_reader(scope, body.production_profile_ref)
        if profile is None or profile.module_id != module_id:
            raise WorkshopFreezeBlocked(
                "installed production profile is missing, drifted, or belongs to another module"
            )
        if prepared.evidence_build_request.required_fact_ids != list(
            profile.evidence_selection.required_facts
        ):
            raise WorkshopFreezeBlocked("required facts drifted from installed profile")

        try:
            bundle = self._production.get_evidence_bundle(
                scope,
                body.evidence_bundle_ref.resource_id,
                body.evidence_bundle_ref.revision,
            )
            self._assert_exact(bundle.content_hash, body.evidence_bundle_ref, "EvidenceBundle")
            if (
                bundle.brief_ref.resource_id != prepared.draft_brief_ref.resource_id
                or bundle.brief_ref.content_hash != prepared.draft_brief_ref.content_hash
            ):
                raise WorkshopFreezeBlocked("EvidenceBundle does not preserve prepared Brief lineage")
            brief = self._production.get_brief(
                scope, bundle.brief_ref.resource_id, bundle.brief_ref.revision
            )
            self._assert_exact(brief.content_hash, bundle.brief_ref, "TaskBrief")
            eval_contract = self._production.get_eval_contract(
                scope, body.eval_contract_ref.resource_id, body.eval_contract_ref.revision
            )
            self._assert_exact(eval_contract.content_hash, body.eval_contract_ref, "EvalContract")
            responsibility = self._production.get_responsibility_plan(
                scope,
                body.responsibility_plan_ref.resource_id,
                body.responsibility_plan_ref.revision,
            )
            self._assert_exact(
                responsibility.content_hash,
                body.responsibility_plan_ref,
                "ResponsibilityPlan",
            )
            preparation_ref = ExactRevisionRef(
                resource_type="PreparationReceipt",
                resource_id=prepared.receipt.preparation_id,
                revision=prepared.receipt.revision,
                content_hash=prepared.receipt.result_hash,
            )
            context = self._production.freeze_production_context(
                scope,
                actor,
                f"{idempotency_key}:production-context:freeze",
                FreezeProductionContextRequest(
                    task_id=brief.task_id,
                    brief_ref=bundle.brief_ref,
                    evidence_bundle_ref=body.evidence_bundle_ref,
                    eval_contract_ref=body.eval_contract_ref,
                    responsibility_plan_ref=body.responsibility_plan_ref,
                    production_profile_ref=body.production_profile_ref,
                    preparation_ref=preparation_ref,
                    profile=module_id,
                ),
            )
        except WorkshopFreezeError:
            raise
        except ProductionContractConflict as exc:
            raise WorkshopFreezeConflict(str(exc)) from exc
        except ProductionContractDependencyBlocked as exc:
            raise WorkshopFreezeBlocked(str(exc)) from exc
        except ProductionContractError as exc:
            raise WorkshopFreezeUnavailable(str(exc)) from exc

        context_ref = ExactRevisionRef(
            resource_type="ProductionContextRevision",
            resource_id=context.context_id,
            revision=context.revision,
            content_hash=context.content_hash,
        )
        return WorkshopFreezeResponse(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            module_id=module_id,
            production_profile_ref=body.production_profile_ref,
            context=context,
            receipt=WorkshopFreezeReceipt(
                request_hash=canonical_hash(
                    {"moduleId": module_id, **body.model_dump(mode="json", by_alias=True)}
                ),
                preparation_ref=preparation_ref,
                production_context_ref=context_ref,
                side_effects=PrepareSideEffectCounters(),
                next_allowed_commands=["compile"],
            ),
        )

    @staticmethod
    def _assert_exact(observed_hash: str, ref: ExactRevisionRef, label: str) -> None:
        if observed_hash != ref.content_hash:
            raise WorkshopFreezeBlocked(f"{label} exact ref drifted")
