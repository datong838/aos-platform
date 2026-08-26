"""BI-W4-06 Principal-scoped application service for investigation Case/Run."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_business_investigation_case import (
    BusinessInvestigationAnalysisType,
    BusinessInvestigationCaseLifecycle,
    BusinessInvestigationCaseRevision,
    BusinessInvestigationCaseStore,
)
from aos_api.ecommerce_business_investigation_projection import (
    BusinessInvestigationProjectionBuilder,
    BusinessInvestigationProjectionReader,
    BusinessInvestigationWorkbenchView,
    CanonicalBusinessInvestigationProjectionReader,
)
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunControl,
    BusinessInvestigationRunLifecycle,
    BusinessInvestigationRunRecord,
    BusinessInvestigationRunRequestOutcome,
    BusinessInvestigationRunStateRevision,
    BusinessInvestigationRunStore,
    BusinessInvestigationRunView,
    BusinessInvestigationTriggerKind,
    BusinessInvestigationUncertainCommand,
)
from aos_api.ecommerce_business_investigation_schedule import (
    BusinessInvestigationSchedulePolicyRevision,
    BusinessInvestigationScheduleConflict,
    BusinessInvestigationSchedulePolicyWrite,
    BusinessInvestigationScheduleStore,
    PutBusinessInvestigationSchedulePolicyRequest,
    TriggerBusinessInvestigationScheduleRequest,
    scheduled_trigger_key,
)
from aos_api.ecommerce_business_investigation_data_command import (
    BusinessInvestigationDataCommandResponse,
    ConfirmBusinessInvestigationDataRequirementCommand,
    EcommerceBusinessInvestigationDataCommandService,
    RequestBusinessInvestigationMissingDataCommand,
)
from aos_api.ecommerce_business_investigation_review_command import (
    BusinessInvestigationStageReviewCommand,
    BusinessInvestigationStageReviewProjection,
    BusinessInvestigationStageReviewResponse,
    EcommerceBusinessInvestigationReviewCommandService,
)
from aos_api.ecommerce_analyst_growth_plan_approval import (
    ApproveGrowthPlanRequest,
    EcommerceAnalystGrowthPlanApprovalService,
    GrowthPlanApprovalResponse,
)
from aos_api.ecommerce_business_investigation_handoff import (
    BusinessInvestigationHandoffCompileResponse,
    CompileBusinessInvestigationHandoffRequest,
    EcommerceBusinessInvestigationHandoffService,
)
from aos_api.tenant_scope import TenantScope


class CreateBusinessInvestigationCaseRequest(AipContractModel):
    case_id: str = Field(min_length=1, max_length=200)
    analysis_type: BusinessInvestigationAnalysisType
    title: str = Field(min_length=1, max_length=500)
    purpose_code: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,119}$")
    channel_ref: InvestigationExactRef
    business_entity_ref: InvestigationExactRef
    entity_channel_binding_ref: InvestigationExactRef
    investigation_profile_ref: InvestigationExactRef
    scope_ref: InvestigationExactRef
    schedule_policy_ref: InvestigationExactRef | None = None


class TransitionBusinessInvestigationCaseRequest(AipContractModel):
    target_lifecycle: BusinessInvestigationCaseLifecycle

    @model_validator(mode="after")
    def _target(self) -> "TransitionBusinessInvestigationCaseRequest":
        if self.target_lifecycle is BusinessInvestigationCaseLifecycle.DRAFT:
            raise ValueError("Case cannot transition back to DRAFT")
        return self


class CreateBusinessInvestigationRunRequest(AipContractModel):
    run_id: str = Field(min_length=1, max_length=200)
    case_ref: InvestigationExactRef
    analysis_type: BusinessInvestigationAnalysisType
    trigger_kind: BusinessInvestigationTriggerKind
    trigger_key: str = Field(min_length=1, max_length=240)


class BusinessInvestigationEmptyCommandRequest(AipContractModel):
    pass


class RequestBusinessInvestigationDataRequest(AipContractModel):
    requirement_ref: InvestigationExactRef

    @model_validator(mode="after")
    def _exact_requirement(self) -> "RequestBusinessInvestigationDataRequest":
        if (
            self.requirement_ref.resource_type != "DataRequirementRevision"
            or not isinstance(self.requirement_ref.revision, int)
        ):
            raise ValueError("requirementRef must be exact DataRequirementRevision")
        return self


class BusinessInvestigationCaseCommandResponse(AipContractModel):
    tenant: TenantContext
    authority: BusinessInvestigationCaseRevision
    replayed: bool


class BusinessInvestigationCaseListResponse(AipContractModel):
    tenant: TenantContext
    items: list[BusinessInvestigationCaseRevision]
    count: int = Field(ge=0)


class BusinessInvestigationRunCommandResponse(AipContractModel):
    tenant: TenantContext
    run: BusinessInvestigationRunView
    outcome: BusinessInvestigationRunRequestOutcome
    replayed: bool


class BusinessInvestigationRunStateCommandResponse(AipContractModel):
    tenant: TenantContext
    authority: BusinessInvestigationRunStateRevision
    replayed: bool


class BusinessInvestigationRunListResponse(AipContractModel):
    tenant: TenantContext
    items: list[BusinessInvestigationRunView]
    count: int = Field(ge=0)


class BusinessInvestigationSchedulePolicyCommandResponse(AipContractModel):
    tenant: TenantContext
    authority: BusinessInvestigationSchedulePolicyRevision
    case_authority: BusinessInvestigationCaseRevision
    replayed: bool


class EcommerceBusinessInvestigationApplication:
    def __init__(
        self,
        case_store: BusinessInvestigationCaseStore | None = None,
        run_store: BusinessInvestigationRunStore | None = None,
        schedule_store: BusinessInvestigationScheduleStore | None = None,
        projection_reader: BusinessInvestigationProjectionReader | None = None,
        data_command_service: EcommerceBusinessInvestigationDataCommandService | None = None,
        review_command_service: EcommerceBusinessInvestigationReviewCommandService | None = None,
        growth_plan_approval_service: EcommerceAnalystGrowthPlanApprovalService | None = None,
        handoff_service: EcommerceBusinessInvestigationHandoffService | None = None,
    ) -> None:
        self._cases = case_store or BusinessInvestigationCaseStore()
        self._runs = run_store or BusinessInvestigationRunStore()
        self._schedules = schedule_store or BusinessInvestigationScheduleStore()
        self._data_commands = (
            data_command_service or EcommerceBusinessInvestigationDataCommandService()
        )
        self._review_commands = (
            review_command_service or EcommerceBusinessInvestigationReviewCommandService()
        )
        self._growth_plan_approvals = (
            growth_plan_approval_service or EcommerceAnalystGrowthPlanApprovalService()
        )
        self._projection = BusinessInvestigationProjectionBuilder(
            projection_reader or CanonicalBusinessInvestigationProjectionReader()
        )
        self._handoffs = handoff_service or EcommerceBusinessInvestigationHandoffService(
            projection=self._projection
        )

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)

    def create_case(
        self,
        scope: TenantScope,
        request: CreateBusinessInvestigationCaseRequest,
        *,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationCaseCommandResponse:
        payload = request.model_dump(by_alias=True, mode="json")
        payload.update(
            schemaVersion="aos.ecommerce.business-investigation-case/v1",
            tenant=self._tenant(scope).model_dump(by_alias=True, mode="json"),
            revision=1,
            version=1,
            contentHash="sha256:" + "0" * 64,
            lifecycle=BusinessInvestigationCaseLifecycle.DRAFT.value,
            createdBy=actor,
            createdAt=occurred_at.isoformat(),
        )
        authority = BusinessInvestigationCaseRevision.model_validate(payload)
        payload["contentHash"] = authority.calculated_content_hash()
        result = self._cases.create_draft(
            scope,
            BusinessInvestigationCaseRevision.model_validate(payload),
            idempotency_key=idempotency_key,
        )
        return BusinessInvestigationCaseCommandResponse(
            tenant=self._tenant(scope), authority=result.authority, replayed=result.replayed
        )

    def transition_case(
        self,
        scope: TenantScope,
        case_id: str,
        request: TransitionBusinessInvestigationCaseRequest,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationCaseCommandResponse:
        result = self._cases.transition(
            scope,
            case_id,
            request.target_lifecycle,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            actor=actor,
            occurred_at=occurred_at,
        )
        return BusinessInvestigationCaseCommandResponse(
            tenant=self._tenant(scope), authority=result.authority, replayed=result.replayed
        )

    def get_case(self, scope: TenantScope, case_id: str) -> BusinessInvestigationCaseRevision:
        return self._cases.get(scope, case_id)

    def list_cases(
        self,
        scope: TenantScope,
        *,
        business_entity_id: str | None,
        limit: int,
    ) -> BusinessInvestigationCaseListResponse:
        items = self._cases.list(scope, business_entity_id=business_entity_id, limit=limit)
        return BusinessInvestigationCaseListResponse(
            tenant=self._tenant(scope), items=items, count=len(items)
        )

    def create_run(
        self,
        scope: TenantScope,
        case_id: str,
        request: CreateBusinessInvestigationRunRequest,
        *,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationRunCommandResponse:
        if request.trigger_kind is BusinessInvestigationTriggerKind.SCHEDULED:
            raise ValueError("scheduled Run must use the canonical SchedulePolicy trigger endpoint")
        if (
            request.case_ref.resource_type != "BusinessInvestigationCaseRevision"
            or request.case_ref.resource_id != case_id
            or not isinstance(request.case_ref.revision, int)
        ):
            raise ValueError("caseRef must exactly match the Case path")
        payload = request.model_dump(by_alias=True, mode="json")
        payload.update(
            schemaVersion="aos.ecommerce.business-investigation-run/v1",
            tenant=self._tenant(scope).model_dump(by_alias=True, mode="json"),
            version=1,
            contentHash="sha256:" + "0" * 64,
            lifecycle=BusinessInvestigationRunLifecycle.PREPARING.value,
            control=BusinessInvestigationRunControl.RUNNING.value,
            createdBy=actor,
            createdAt=occurred_at.isoformat(),
        )
        authority = BusinessInvestigationRunRecord.model_validate(payload)
        payload["contentHash"] = authority.calculated_content_hash()
        write = self._runs.request(
            scope,
            BusinessInvestigationRunRecord.model_validate(payload),
            idempotency_key=idempotency_key,
        )
        return BusinessInvestigationRunCommandResponse(
            tenant=self._tenant(scope),
            run=self._runs.get(scope, write.authority.run_id),
            outcome=write.outcome,
            replayed=write.replayed,
        )

    def put_schedule_policy(
        self,
        scope: TenantScope,
        case_id: str,
        request: PutBusinessInvestigationSchedulePolicyRequest,
        *,
        expected_policy_revision: int,
        expected_case_version: int,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationSchedulePolicyCommandResponse:
        if request.case_ref.resource_type != "BusinessInvestigationCaseRevision" or (
            request.case_ref.resource_id != case_id
            or request.case_ref.revision != expected_case_version
        ):
            raise ValueError("caseRef must exactly match Case path and expected version")
        replay = self._schedules.find_put_receipt(scope, idempotency_key)
        if replay is not None:
            authority = replay.authority
            if (
                replay.expected_policy_revision != expected_policy_revision
                or replay.expected_case_version != expected_case_version
                or authority.schedule_policy_id != request.schedule_policy_id
                or authority.case_ref != request.case_ref
                or authority.analysis_type is not request.analysis_type
                or authority.policy_kind is not request.policy_kind
                or authority.cadence is not request.cadence
                or authority.enabled is not request.enabled
                or authority.overlap_policy != request.overlap_policy
                or authority.timezone != request.timezone
                or authority.weekly_day != request.weekly_day
                or authority.local_time != request.local_time
            ):
                raise BusinessInvestigationScheduleConflict(
                    "SchedulePolicy idempotency conflict"
                )
            return BusinessInvestigationSchedulePolicyCommandResponse(
                tenant=self._tenant(scope),
                authority=authority,
                case_authority=replay.case_authority,
                replayed=True,
            )
        previous_case = self._cases.get(scope, case_id)
        if previous_case.version != expected_case_version or request.case_ref.content_hash != previous_case.content_hash:
            raise ValueError("caseRef does not match current Case authority")
        if request.analysis_type is not previous_case.analysis_type:
            raise ValueError("SchedulePolicy analysisType must match Case")
        previous_policy = None
        if expected_policy_revision:
            previous_policy = self._schedules.get(scope, request.schedule_policy_id)
            if previous_policy.revision != expected_policy_revision:
                raise ValueError("SchedulePolicy expected revision conflict")
        payload = request.model_dump(by_alias=True, mode="json")
        payload.update(
            schemaVersion="aos.ecommerce.business-investigation-schedule-policy/v1",
            tenant=self._tenant(scope).model_dump(by_alias=True, mode="json"),
            revision=expected_policy_revision + 1,
            version=expected_policy_revision + 1,
            priorRef=(
                None
                if previous_policy is None
                else {
                    "resourceType": "SchedulePolicyRevision",
                    "resourceId": previous_policy.schedule_policy_id,
                    "revision": previous_policy.revision,
                    "contentHash": previous_policy.content_hash,
                }
            ),
            contentHash="sha256:" + "0" * 64,
            createdBy=actor,
            createdAt=occurred_at.isoformat(),
        )
        policy = BusinessInvestigationSchedulePolicyRevision.model_validate(payload)
        payload["contentHash"] = policy.calculated_content_hash()
        policy = BusinessInvestigationSchedulePolicyRevision.model_validate(payload)
        if previous_policy is not None:
            policy.validate_successor(previous_policy)
        case_payload = previous_case.model_dump(by_alias=True, mode="json")
        case_payload.update(
            revision=expected_case_version + 1,
            version=expected_case_version + 1,
            priorRef={
                "resourceType": "BusinessInvestigationCaseRevision",
                "resourceId": previous_case.case_id,
                "revision": previous_case.revision,
                "contentHash": previous_case.content_hash,
            },
            schedulePolicyRef={
                "resourceType": "SchedulePolicyRevision",
                "resourceId": policy.schedule_policy_id,
                "revision": policy.revision,
                "contentHash": policy.content_hash,
            },
            contentHash="sha256:" + "0" * 64,
            createdBy=actor,
            createdAt=occurred_at.isoformat(),
        )
        case_authority = BusinessInvestigationCaseRevision.model_validate(case_payload)
        case_payload["contentHash"] = case_authority.calculated_content_hash()
        case_authority = BusinessInvestigationCaseRevision.model_validate(case_payload)
        case_authority.validate_successor(previous_case)
        write: BusinessInvestigationSchedulePolicyWrite = self._schedules.put_and_bind_case(
            scope,
            policy,
            case_authority,
            expected_policy_revision=expected_policy_revision,
            expected_case_version=expected_case_version,
            idempotency_key=idempotency_key,
        )
        return BusinessInvestigationSchedulePolicyCommandResponse(
            tenant=self._tenant(scope),
            authority=write.authority,
            case_authority=write.case_authority,
            replayed=write.replayed,
        )

    def get_schedule_policy(
        self, scope: TenantScope, schedule_policy_id: str
    ) -> BusinessInvestigationSchedulePolicyRevision:
        return self._schedules.get(scope, schedule_policy_id)

    def trigger_schedule_policy(
        self,
        scope: TenantScope,
        schedule_policy_id: str,
        request: TriggerBusinessInvestigationScheduleRequest,
        *,
        expected_policy_revision: int,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationRunCommandResponse:
        policy = self._schedules.get(scope, schedule_policy_id)
        if policy.revision != expected_policy_revision or request.schedule_policy_ref != InvestigationExactRef(
            resourceType="SchedulePolicyRevision",
            resourceId=policy.schedule_policy_id,
            revision=policy.revision,
            contentHash=policy.content_hash,
        ):
            raise ValueError("schedulePolicyRef does not match current policy authority")
        if not policy.enabled:
            raise ValueError("SchedulePolicy is disabled")
        case = self._cases.get(scope, policy.case_ref.resource_id)
        if case.schedule_policy_ref != request.schedule_policy_ref or case.lifecycle is not BusinessInvestigationCaseLifecycle.ACTIVE:
            raise ValueError("SchedulePolicy is not bound to an ACTIVE Case")
        payload = {
            "schemaVersion": "aos.ecommerce.business-investigation-run/v1",
            "tenant": self._tenant(scope).model_dump(by_alias=True, mode="json"),
            "runId": request.run_id,
            "version": 1,
            "contentHash": "sha256:" + "0" * 64,
            "caseRef": {
                "resourceType": "BusinessInvestigationCaseRevision",
                "resourceId": case.case_id,
                "revision": case.revision,
                "contentHash": case.content_hash,
            },
            "analysisType": policy.analysis_type.value,
            "triggerKind": BusinessInvestigationTriggerKind.SCHEDULED.value,
            "triggerKey": scheduled_trigger_key(policy, request.scheduled_at),
            "lifecycle": BusinessInvestigationRunLifecycle.PREPARING.value,
            "control": BusinessInvestigationRunControl.RUNNING.value,
            "createdBy": actor,
            "createdAt": occurred_at.isoformat(),
        }
        authority = BusinessInvestigationRunRecord.model_validate(payload)
        payload["contentHash"] = authority.calculated_content_hash()
        write = self._runs.request(
            scope,
            BusinessInvestigationRunRecord.model_validate(payload),
            idempotency_key=idempotency_key,
        )
        return BusinessInvestigationRunCommandResponse(
            tenant=self._tenant(scope),
            run=self._runs.get(scope, write.authority.run_id),
            outcome=write.outcome,
            replayed=write.replayed,
        )

    def get_run(self, scope: TenantScope, run_id: str) -> BusinessInvestigationRunView:
        return self._runs.get(scope, run_id)

    def get_run_view(
        self, scope: TenantScope, run_id: str, *, observed_at: datetime
    ) -> BusinessInvestigationWorkbenchView:
        return self._projection.build(scope, run_id, observed_at=observed_at)

    def list_runs(
        self,
        scope: TenantScope,
        case_id: str,
        *,
        limit: int,
    ) -> BusinessInvestigationRunListResponse:
        self._cases.get(scope, case_id)
        items = self._runs.list_for_case(scope, case_id, limit=limit)
        return BusinessInvestigationRunListResponse(
            tenant=self._tenant(scope), items=items, count=len(items)
        )

    def transition_run_control(
        self,
        scope: TenantScope,
        run_id: str,
        target: BusinessInvestigationRunControl,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationRunStateCommandResponse:
        result = self._runs.transition_control(
            scope,
            run_id,
            target,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            actor=actor,
            occurred_at=occurred_at,
        )
        return BusinessInvestigationRunStateCommandResponse(
            tenant=self._tenant(scope), authority=result.authority, replayed=result.replayed
        )

    def request_run_data(
        self,
        scope: TenantScope,
        run_id: str,
        request: RequestBusinessInvestigationDataRequest,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationRunStateCommandResponse:
        result = self._runs.request_data(
            scope,
            run_id,
            request.requirement_ref,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            actor=actor,
            occurred_at=occurred_at,
        )
        return BusinessInvestigationRunStateCommandResponse(
            tenant=self._tenant(scope), authority=result.authority, replayed=result.replayed
        )

    def request_run_missing_data(
        self,
        scope: TenantScope,
        run_id: str,
        request: RequestBusinessInvestigationMissingDataCommand,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationDataCommandResponse:
        return self._data_commands.request_missing_data(
            scope,
            run_id,
            request,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            actor=actor,
            occurred_at=occurred_at,
        )

    def confirm_run_data_requirement(
        self,
        scope: TenantScope,
        run_id: str,
        request: ConfirmBusinessInvestigationDataRequirementCommand,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationDataCommandResponse:
        return self._data_commands.confirm_requirement(
            scope,
            run_id,
            request,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            actor=actor,
            occurred_at=occurred_at,
        )

    def get_run_stage_review(
        self, scope: TenantScope, run_id: str
    ) -> BusinessInvestigationStageReviewProjection:
        return self._review_commands.projection(scope, run_id)

    def review_run_stage(
        self,
        scope: TenantScope,
        run_id: str,
        request: BusinessInvestigationStageReviewCommand,
        *,
        expected_state_version: int,
        idempotency_key: str,
        actor: str,
    ) -> BusinessInvestigationStageReviewResponse:
        return self._review_commands.review_stage(
            scope,
            run_id,
            request,
            expected_state_version=expected_state_version,
            idempotency_key=idempotency_key,
            actor=actor,
        )

    def approve_growth_plan(
        self,
        scope: TenantScope,
        plan_id: str,
        request: ApproveGrowthPlanRequest,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
    ) -> GrowthPlanApprovalResponse:
        return self._growth_plan_approvals.approve(
            scope,
            plan_id,
            request,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            actor=actor,
        )

    def compile_handoff(
        self,
        scope: TenantScope,
        run_id: str,
        request: CompileBusinessInvestigationHandoffRequest,
        *,
        roles: list[str],
        principal_markings: list[str],
    ) -> BusinessInvestigationHandoffCompileResponse:
        return self._handoffs.compile(
            scope,
            run_id,
            request,
            roles=roles,
            principal_markings=principal_markings,
        )

    def mark_run_unknown(
        self,
        scope: TenantScope,
        run_id: str,
        uncertain_command: BusinessInvestigationUncertainCommand,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationRunStateCommandResponse:
        result = self._runs.mark_unknown(
            scope,
            run_id,
            uncertain_command,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            actor=actor,
            occurred_at=occurred_at,
        )
        return BusinessInvestigationRunStateCommandResponse(
            tenant=self._tenant(scope), authority=result.authority, replayed=result.replayed
        )

    def begin_run_reconcile(
        self,
        scope: TenantScope,
        run_id: str,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationRunStateCommandResponse:
        result = self._runs.begin_reconcile(
            scope,
            run_id,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            actor=actor,
            occurred_at=occurred_at,
        )
        return BusinessInvestigationRunStateCommandResponse(
            tenant=self._tenant(scope), authority=result.authority, replayed=result.replayed
        )


__all__ = [
    "BusinessInvestigationCaseCommandResponse",
    "BusinessInvestigationCaseListResponse",
    "BusinessInvestigationEmptyCommandRequest",
    "BusinessInvestigationRunCommandResponse",
    "BusinessInvestigationRunListResponse",
    "BusinessInvestigationRunStateCommandResponse",
    "BusinessInvestigationSchedulePolicyCommandResponse",
    "CreateBusinessInvestigationCaseRequest",
    "CreateBusinessInvestigationRunRequest",
    "EcommerceBusinessInvestigationApplication",
    "RequestBusinessInvestigationDataRequest",
    "PutBusinessInvestigationSchedulePolicyRequest",
    "TriggerBusinessInvestigationScheduleRequest",
    "TransitionBusinessInvestigationCaseRequest",
]
