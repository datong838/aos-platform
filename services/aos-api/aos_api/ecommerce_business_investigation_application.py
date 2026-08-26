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


class EcommerceBusinessInvestigationApplication:
    def __init__(
        self,
        case_store: BusinessInvestigationCaseStore | None = None,
        run_store: BusinessInvestigationRunStore | None = None,
        projection_reader: BusinessInvestigationProjectionReader | None = None,
    ) -> None:
        self._cases = case_store or BusinessInvestigationCaseStore()
        self._runs = run_store or BusinessInvestigationRunStore()
        self._projection = BusinessInvestigationProjectionBuilder(
            projection_reader or CanonicalBusinessInvestigationProjectionReader()
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
    "CreateBusinessInvestigationCaseRequest",
    "CreateBusinessInvestigationRunRequest",
    "EcommerceBusinessInvestigationApplication",
    "RequestBusinessInvestigationDataRequest",
    "TransitionBusinessInvestigationCaseRequest",
]
