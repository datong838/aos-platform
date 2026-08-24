"""Server-side, zero-execution ecommerce Workshop prepare aggregate."""
from __future__ import annotations

from datetime import datetime, timezone
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
    ContractBlocker,
    CreateBriefRequest,
    ExactRevisionRef,
    ReviseBriefRequest,
    TaskBriefRevision,
)
from aos_api.aip_production_profile_contracts import ProductionProfile
from aos_api.aip_responsibility_template_authority import (
    InstalledProductionProfileResolver,
)
from aos_api.ecommerce_workshop_prepare_contracts import (
    BriefDiffChange,
    EcommerceWorkshopPrepareRequest,
    EcommerceWorkshopPrepareResponse,
    EvidenceBuildReadiness,
    EvidenceBuildRequestRevision,
    PreparationReceipt,
    PrepareSideEffectCounters,
    RecommendationCoverage,
    ResponsibilityRecommendationRevision,
    ResponsibilitySlotRecommendation,
)
from aos_api.ecommerce_workshop_prepare_store import (
    EcommerceWorkshopPrepareStore,
    PreparationIdempotencyConflict,
    PreparationStoreError,
)
from aos_api.tenant_scope import TenantScope


class PrepareError(RuntimeError):
    code = "WORKSHOP_PREPARE_ERROR"


class PrepareConflict(PrepareError):
    code = "WORKSHOP_REVISION_CONFLICT"


class PrepareDependencyBlocked(PrepareError):
    code = "WORKSHOP_PREPARE_DEPENDENCY_BLOCKED"


class PrepareUnavailable(PrepareError):
    code = "WORKSHOP_PREPARE_UNAVAILABLE"


class ProfileReader(Protocol):
    def __call__(
        self, scope: TenantScope, ref: ExactRevisionRef
    ) -> ProductionProfile | None: ...


class BriefAuthority(Protocol):
    def create_brief(
        self, scope: TenantScope, actor: str, key: str, body: CreateBriefRequest
    ) -> TaskBriefRevision: ...

    def revise_brief(
        self,
        scope: TenantScope,
        actor: str,
        brief_id: str,
        key: str,
        body: ReviseBriefRequest,
    ) -> TaskBriefRevision: ...

    def get_brief(
        self, scope: TenantScope, brief_id: str, revision: int | None = None
    ) -> TaskBriefRevision: ...


class EcommerceWorkshopPrepareService:
    def __init__(
        self,
        *,
        preparation_store: EcommerceWorkshopPrepareStore | None = None,
        brief_authority: BriefAuthority | None = None,
        profile_reader: ProfileReader | None = None,
    ) -> None:
        self._preparations = preparation_store or EcommerceWorkshopPrepareStore()
        self._briefs = brief_authority or AipProductionContractStore()
        resolver = InstalledProductionProfileResolver()
        self._profile_reader = profile_reader or resolver.load_profile

    def prepare(
        self,
        scope: TenantScope,
        *,
        actor: str,
        module_id: str,
        idempotency_key: str,
        body: EcommerceWorkshopPrepareRequest,
    ) -> EcommerceWorkshopPrepareResponse:
        payload = {"moduleId": module_id, **body.model_dump(mode="json", by_alias=True)}
        request_hash = canonical_hash(payload)
        try:
            intent = self._preparations.begin(
                scope,
                actor=actor,
                module_id=module_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                request_body=payload,
            )
        except PreparationIdempotencyConflict as exc:
            raise PrepareConflict(str(exc)) from exc
        except PreparationStoreError as exc:
            raise PrepareUnavailable(str(exc)) from exc
        if intent.result_body is not None:
            replay = EcommerceWorkshopPrepareResponse.model_validate(intent.result_body)
            return replay.model_copy(
                update={"receipt": replay.receipt.model_copy(update={"replay": True})}
            )

        profile = self._profile_reader(scope, body.production_profile_ref)
        if profile is None or profile.module_id != module_id:
            raise PrepareDependencyBlocked(
                "installed production profile is missing, drifted, or belongs to another module"
            )

        previous: TaskBriefRevision | None = None
        try:
            if body.brief.existing_brief_ref is None:
                brief = self._briefs.create_brief(
                    scope,
                    actor,
                    f"{idempotency_key}:brief:create",
                    CreateBriefRequest(
                        task_id=body.brief.task_id,
                        brief_type=body.brief.brief_type,
                        schema_ref=body.brief.schema_ref,
                        spec=body.brief.spec,
                    ),
                )
            else:
                exact = body.brief.existing_brief_ref
                previous = self._briefs.get_brief(
                    scope, exact.resource_id, exact.revision
                )
                if previous.content_hash != exact.content_hash:
                    raise PrepareDependencyBlocked("draft Brief exact ref drifted")
                if previous.task_id != body.brief.task_id:
                    raise PrepareDependencyBlocked("draft Brief belongs to another task")
                brief = self._briefs.revise_brief(
                    scope,
                    actor,
                    exact.resource_id,
                    f"{idempotency_key}:brief:revise",
                    ReviseBriefRequest(
                        expected_version=body.brief.expected_version,
                        brief_type=body.brief.brief_type,
                        schema_ref=body.brief.schema_ref,
                        spec=body.brief.spec,
                    ),
                )
        except ProductionContractConflict as exc:
            raise PrepareConflict(str(exc)) from exc
        except ProductionContractDependencyBlocked as exc:
            raise PrepareDependencyBlocked(str(exc)) from exc
        except ProductionContractError as exc:
            raise PrepareUnavailable(str(exc)) from exc

        brief_ref = ExactRevisionRef(
            resource_type="TaskBriefRevision",
            resource_id=brief.brief_id,
            revision=brief.revision,
            content_hash=brief.content_hash,
        )
        brief_diff = self._brief_diff(previous, brief)
        evidence_request = self._evidence_request(
            intent.preparation_id, brief_ref, profile, body
        )
        recommendation = self._recommendation(
            intent.preparation_id, brief_ref, profile, body.production_profile_ref
        )
        created_at = datetime.now(timezone.utc)
        core = {
            "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
            "moduleId": module_id,
            "draftBriefRef": brief_ref.model_dump(mode="json", by_alias=True),
            "briefDiff": [item.model_dump(mode="json", by_alias=True) for item in brief_diff],
            "evidenceBuildRequest": evidence_request.model_dump(mode="json", by_alias=True),
            "responsibilityRecommendation": recommendation.model_dump(mode="json", by_alias=True),
        }
        result_hash = canonical_hash(core)
        response = EcommerceWorkshopPrepareResponse(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            module_id=module_id,
            draft_brief_ref=brief_ref,
            brief_diff=brief_diff,
            evidence_build_request=evidence_request,
            responsibility_recommendation=recommendation,
            receipt=PreparationReceipt(
                preparation_id=intent.preparation_id,
                request_hash=request_hash,
                result_hash=result_hash,
                replay=False,
                input_counts={
                    "subjectRefs": len(body.subject_refs),
                    "canonicalEvidenceRefs": len(body.canonical_evidence_refs),
                    "requiredFacts": len(profile.evidence_selection.required_facts),
                    "responsibilitySlots": len(profile.responsibility.slots),
                },
                output_counts={
                    "draftBriefs": 1,
                    "evidenceBuildRequests": 1,
                    "responsibilityRecommendations": 1,
                    "evidenceBundles": 0,
                    "responsibilityPlans": 0,
                },
                side_effects=PrepareSideEffectCounters(),
                next_allowed_commands=[],
                created_at=created_at,
            ),
        )
        serialized = response.model_dump(mode="json", by_alias=True)
        try:
            self._preparations.complete(
                scope,
                actor=actor,
                preparation_id=intent.preparation_id,
                request_hash=request_hash,
                result_hash=result_hash,
                result_body=serialized,
            )
        except PreparationStoreError as exc:
            raise PrepareUnavailable(str(exc)) from exc
        return response

    @staticmethod
    def _brief_diff(
        previous: TaskBriefRevision | None, current: TaskBriefRevision
    ) -> list[BriefDiffChange]:
        if previous is None:
            return [
                BriefDiffChange(
                    field="brief",
                    before=None,
                    after=current.spec,
                    impact="draft_created",
                )
            ]
        changes: list[BriefDiffChange] = []
        if previous.brief_type != current.brief_type:
            changes.append(
                BriefDiffChange(
                    field="briefType",
                    before=previous.brief_type,
                    after=current.brief_type,
                    impact="review_required",
                )
            )
        if previous.spec != current.spec:
            changes.append(
                BriefDiffChange(
                    field="spec",
                    before=previous.spec,
                    after=current.spec,
                    impact="review_required",
                )
            )
        return changes

    @staticmethod
    def _evidence_request(
        preparation_id: str,
        brief_ref: ExactRevisionRef,
        profile: ProductionProfile,
        body: EcommerceWorkshopPrepareRequest,
    ) -> EvidenceBuildRequestRevision:
        required = list(profile.evidence_selection.required_facts)
        blockers = [
            ContractBlocker(code="EVIDENCE_FACT_NOT_CANONICALLY_RESOLVED", message=fact)
            for fact in required
        ]
        payload = {
            "briefRef": brief_ref.model_dump(mode="json", by_alias=True),
            "profileRef": body.production_profile_ref.model_dump(mode="json", by_alias=True),
            "requiredFactIds": required,
            "evidenceRefs": [
                item.model_dump(mode="json", by_alias=True)
                for item in body.canonical_evidence_refs
            ],
        }
        return EvidenceBuildRequestRevision(
            request_id=f"evidence-build-{preparation_id.removeprefix('preparation-')}",
            brief_ref=brief_ref,
            production_profile_ref=body.production_profile_ref,
            required_fact_ids=required,
            subject_refs=body.subject_refs,
            canonical_evidence_refs=body.canonical_evidence_refs,
            cutoff_at=body.cutoff_at,
            purpose=body.purpose,
            marking=body.marking,
            readiness=(EvidenceBuildReadiness.BLOCKED if required else EvidenceBuildReadiness.SATISFIED),
            missing_fact_ids=required,
            blockers=blockers,
            content_hash=canonical_hash(payload),
        )

    @staticmethod
    def _recommendation(
        preparation_id: str,
        brief_ref: ExactRevisionRef,
        profile: ProductionProfile,
        profile_ref: ExactRevisionRef,
    ) -> ResponsibilityRecommendationRevision:
        slots = [
            ResponsibilitySlotRecommendation(
                slot_id=slot.slot_id,
                responsibility_type=slot.responsibility_type,
                atomic_skill_ids=slot.atomic_skill_ids,
                protected=slot.protected,
                merge_allowed=slot.merge_allowed,
                return_stage=slot.return_stage,
                readiness="blocked",
                blockers=[
                    ContractBlocker(
                        code="ASSIGNEE_EXACT_BINDING_NOT_RESOLVED",
                        message="canonical digital-colleague binding is required",
                    )
                ],
            )
            for slot in profile.responsibility.slots
        ]
        uncovered = [slot.slot_id for slot in profile.responsibility.slots]
        blockers = [
            ContractBlocker(
                code="RESPONSIBILITY_ASSIGNEE_COVERAGE_BLOCKED",
                message="one or more responsibility slots have no exact assignee binding",
            )
        ] if uncovered else []
        payload = {
            "briefRef": brief_ref.model_dump(mode="json", by_alias=True),
            "profileRef": profile_ref.model_dump(mode="json", by_alias=True),
            "slots": [slot.model_dump(mode="json", by_alias=True) for slot in slots],
        }
        return ResponsibilityRecommendationRevision(
            recommendation_id=f"responsibility-recommendation-{preparation_id.removeprefix('preparation-')}",
            brief_ref=brief_ref,
            production_profile_ref=profile_ref,
            slots=slots,
            coverage=(RecommendationCoverage.BLOCKED if uncovered else RecommendationCoverage.COMPLETE),
            uncovered_slot_ids=uncovered,
            blockers=blockers,
            content_hash=canonical_hash(payload),
        )
