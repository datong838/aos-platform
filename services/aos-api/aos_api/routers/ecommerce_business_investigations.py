"""BI-W4-06 canonical HTTP adapter for ecommerce business investigations."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Security, status
from fastapi.security import HTTPBearer

from aos_api.auth import Principal, require_principal
from aos_api.ecommerce_business_investigation_application import (
    BusinessInvestigationCaseCommandResponse,
    BusinessInvestigationCaseListResponse,
    BusinessInvestigationEmptyCommandRequest,
    BusinessInvestigationRunCommandResponse,
    BusinessInvestigationRunListResponse,
    BusinessInvestigationRunStateCommandResponse,
    BusinessInvestigationSchedulePolicyCommandResponse,
    CreateBusinessInvestigationCaseRequest,
    CreateBusinessInvestigationRunRequest,
    EcommerceBusinessInvestigationApplication,
    RequestBusinessInvestigationDataRequest,
    PutBusinessInvestigationSchedulePolicyRequest,
    TriggerBusinessInvestigationScheduleRequest,
    TransitionBusinessInvestigationCaseRequest,
)
from aos_api.ecommerce_business_investigation_data_command import (
    BusinessInvestigationDataCommandConflict,
    BusinessInvestigationDataCommandResponse,
    ConfirmBusinessInvestigationDataRequirementCommand,
    RequestBusinessInvestigationMissingDataCommand,
)
from aos_api.ecommerce_business_investigation_case import (
    BusinessInvestigationAnalysisType,
    BusinessInvestigationCaseConflict,
    BusinessInvestigationCaseNotFound,
    BusinessInvestigationCaseRevision,
)
from aos_api.ecommerce_business_investigation_case_selection import (
    BusinessInvestigationCaseSelection,
    BusinessInvestigationCaseSelectionBlocked,
    BusinessInvestigationCaseSelectionConflict,
)
from aos_api.ecommerce_business_investigation_projection import (
    BusinessInvestigationProjectionError,
    BusinessInvestigationProjectionNotFound,
    BusinessInvestigationWorkbenchView,
)
from aos_api.ecommerce_business_investigation_review_command import (
    BusinessInvestigationReviewCommandBlocked,
    BusinessInvestigationStageReviewCommand,
    BusinessInvestigationStageReviewProjection,
    BusinessInvestigationStageReviewResponse,
)
from aos_api.ecommerce_business_investigation_handoff import (
    BusinessInvestigationHandoffBlocked,
    BusinessInvestigationHandoffCompileResponse,
    CompileBusinessInvestigationHandoffRequest,
)
from aos_api.ecommerce_analyst_authority_store import (
    AnalystAuthorityConflict,
    AnalystAuthorityIdempotencyConflict,
    AnalystAuthorityNotFound,
)
from aos_api.ecommerce_analyst_growth_plan_approval import (
    ApproveGrowthPlanRequest,
    GrowthPlanApprovalBlocked,
    GrowthPlanApprovalResponse,
)
from aos_api.aip_production_contract_store import (
    ProductionContractConflict,
    ProductionContractDependencyBlocked,
    ProductionContractNotFound,
)
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunConflict,
    BusinessInvestigationRunControl,
    BusinessInvestigationRunNotFound,
    BusinessInvestigationRunView,
)
from aos_api.ecommerce_business_investigation_schedule import (
    BusinessInvestigationScheduleConflict,
    BusinessInvestigationScheduleNotFound,
    BusinessInvestigationSchedulePolicyRevision,
)
from aos_api.errors import ApiError, ErrorBody
from aos_api.tenant_scope import TenantScope


_bearer = HTTPBearer(auto_error=False)
router = APIRouter(
    prefix="/v1/ecommerce/investigations",
    tags=["ecommerce-business-investigations"],
    dependencies=[Security(_bearer)],
)
_ERRORS = {
    400: {"model": ErrorBody},
    401: {"model": ErrorBody},
    403: {"model": ErrorBody},
    404: {"model": ErrorBody},
    409: {"model": ErrorBody},
    422: {"model": ErrorBody},
    503: {"model": ErrorBody},
}
PrincipalDependency = Annotated[Principal, Depends(require_principal)]
ResourceIdPath = Annotated[
    str,
    Path(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$"),
]
_DATA_WRITE_ROLES = {"admin", "developer", "data-owner"}
_REVIEW_WRITE_ROLES = {"admin", "developer", "reviewer"}


@lru_cache(maxsize=1)
def get_business_investigation_application() -> EcommerceBusinessInvestigationApplication:
    return EcommerceBusinessInvestigationApplication()


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _idempotency_key(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 200:
        raise ApiError(
            code="BUSINESS_INVESTIGATION_INVALID_IDEMPOTENCY_KEY",
            message="Idempotency-Key must be 1..200 characters",
            status_code=400,
        )
    return cleaned


def _expected_version(value: str) -> int:
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] == '"':
        cleaned = cleaned[1:-1]
    if not cleaned.isdigit() or int(cleaned) < 1:
        raise ApiError(
            code="BUSINESS_INVESTIGATION_INVALID_IF_MATCH",
            message="If-Match must contain one positive integer version",
            status_code=400,
        )
    return int(cleaned)


def _map_error(exc: Exception) -> ApiError:
    if isinstance(exc, ApiError):
        return exc
    if isinstance(
        exc,
        (
            BusinessInvestigationCaseNotFound,
            BusinessInvestigationRunNotFound,
            BusinessInvestigationProjectionNotFound,
            BusinessInvestigationScheduleNotFound,
            ProductionContractNotFound,
            AnalystAuthorityNotFound,
        ),
    ):
        return ApiError(
            code="BUSINESS_INVESTIGATION_NOT_FOUND",
            message="business investigation resource is not visible",
            status_code=404,
        )
    if isinstance(
        exc,
        (
            BusinessInvestigationCaseConflict,
            BusinessInvestigationRunConflict,
            BusinessInvestigationScheduleConflict,
            BusinessInvestigationDataCommandConflict,
            BusinessInvestigationReviewCommandBlocked,
            ProductionContractConflict,
            ProductionContractDependencyBlocked,
            AnalystAuthorityConflict,
            AnalystAuthorityIdempotencyConflict,
            GrowthPlanApprovalBlocked,
            BusinessInvestigationHandoffBlocked,
            BusinessInvestigationCaseSelectionBlocked,
            BusinessInvestigationCaseSelectionConflict,
        ),
    ):
        return ApiError(
            code="BUSINESS_INVESTIGATION_CONFLICT",
            message=str(exc),
            status_code=409,
        )
    if isinstance(exc, BusinessInvestigationProjectionError):
        return ApiError(
            code="BUSINESS_INVESTIGATION_AUTHORITY_UNAVAILABLE",
            message="business investigation authority failed closed",
            status_code=503,
        )
    if isinstance(exc, ValueError):
        return ApiError(
            code="BUSINESS_INVESTIGATION_INVALID_ARGUMENT",
            message=str(exc),
            status_code=422,
        )
    return ApiError(
        code="BUSINESS_INVESTIGATION_AUTHORITY_UNAVAILABLE",
        message="business investigation authority failed closed",
        status_code=503,
    )


def _require_data_write_role(principal: Principal) -> None:
    if not _DATA_WRITE_ROLES.intersection(principal.roles):
        raise ApiError(
            code="BUSINESS_INVESTIGATION_DATA_WRITE_FORBIDDEN",
            message="Principal role does not allow DataRequirement commands",
            status_code=403,
        )


def _require_review_write_role(principal: Principal) -> None:
    if not _REVIEW_WRITE_ROLES.intersection(principal.roles):
        raise ApiError(
            code="BUSINESS_INVESTIGATION_REVIEW_WRITE_FORBIDDEN",
            message="Principal role does not allow stage review commands",
            status_code=403,
        )


@router.get(
    "/case-selection",
    response_model=BusinessInvestigationCaseSelection,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationCaseSelectionGet",
)
def get_case_selection(
    principal: PrincipalDependency,
    analysis_type: BusinessInvestigationAnalysisType = Query(alias="analysisType"),
    application: EcommerceBusinessInvestigationApplication = Depends(
        get_business_investigation_application
    ),
) -> BusinessInvestigationCaseSelection:
    try:
        return application.get_case_selection(_scope(principal), analysis_type)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/cases",
    response_model=BusinessInvestigationCaseListResponse,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationCaseList",
)
def list_cases(
    principal: PrincipalDependency,
    business_entity_id: str | None = Query(default=None, alias="businessEntityId", min_length=1, max_length=240),
    limit: int = Query(default=50, ge=1, le=200),
    application: EcommerceBusinessInvestigationApplication = Depends(get_business_investigation_application),
) -> BusinessInvestigationCaseListResponse:
    try:
        return application.list_cases(
            _scope(principal), business_entity_id=business_entity_id, limit=limit
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/cases",
    response_model=BusinessInvestigationCaseCommandResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationCaseCreate",
)
def create_case(
    body: CreateBusinessInvestigationCaseRequest,
    principal: PrincipalDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    application: EcommerceBusinessInvestigationApplication = Depends(get_business_investigation_application),
) -> BusinessInvestigationCaseCommandResponse:
    try:
        return application.create_case(
            _scope(principal),
            body,
            idempotency_key=_idempotency_key(idempotency_key),
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/cases/{case_id}",
    response_model=BusinessInvestigationCaseRevision,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationCaseGet",
)
def get_case(
    case_id: ResourceIdPath,
    principal: PrincipalDependency,
    application: EcommerceBusinessInvestigationApplication = Depends(get_business_investigation_application),
) -> BusinessInvestigationCaseRevision:
    try:
        return application.get_case(_scope(principal), case_id)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/cases/{case_id}:transition",
    response_model=BusinessInvestigationCaseCommandResponse,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationCaseTransition",
)
def transition_case(
    case_id: ResourceIdPath,
    body: TransitionBusinessInvestigationCaseRequest,
    principal: PrincipalDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    application: EcommerceBusinessInvestigationApplication = Depends(get_business_investigation_application),
) -> BusinessInvestigationCaseCommandResponse:
    try:
        return application.transition_case(
            _scope(principal),
            case_id,
            body,
            expected_version=_expected_version(if_match),
            idempotency_key=_idempotency_key(idempotency_key),
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/cases/{case_id}/runs",
    response_model=BusinessInvestigationRunListResponse,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationRunList",
)
def list_runs(
    case_id: ResourceIdPath,
    principal: PrincipalDependency,
    limit: int = Query(default=50, ge=1, le=200),
    application: EcommerceBusinessInvestigationApplication = Depends(get_business_investigation_application),
) -> BusinessInvestigationRunListResponse:
    try:
        return application.list_runs(_scope(principal), case_id, limit=limit)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/cases/{case_id}/runs",
    response_model=BusinessInvestigationRunCommandResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationRunCreate",
)
def create_run(
    case_id: ResourceIdPath,
    body: CreateBusinessInvestigationRunRequest,
    principal: PrincipalDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    application: EcommerceBusinessInvestigationApplication = Depends(get_business_investigation_application),
) -> BusinessInvestigationRunCommandResponse:
    try:
        return application.create_run(
            _scope(principal),
            case_id,
            body,
            idempotency_key=_idempotency_key(idempotency_key),
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/cases/{case_id}/schedule-policies",
    response_model=BusinessInvestigationSchedulePolicyCommandResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationSchedulePolicyCreate",
)
def create_schedule_policy(
    case_id: ResourceIdPath,
    body: PutBusinessInvestigationSchedulePolicyRequest,
    principal: PrincipalDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    application: EcommerceBusinessInvestigationApplication = Depends(
        get_business_investigation_application
    ),
) -> BusinessInvestigationSchedulePolicyCommandResponse:
    try:
        return application.put_schedule_policy(
            _scope(principal),
            case_id,
            body,
            expected_policy_revision=0,
            expected_case_version=_expected_version(if_match),
            idempotency_key=_idempotency_key(idempotency_key),
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/schedule-policies/{schedule_policy_id}",
    response_model=BusinessInvestigationSchedulePolicyRevision,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationSchedulePolicyGet",
)
def get_schedule_policy(
    schedule_policy_id: ResourceIdPath,
    principal: PrincipalDependency,
    application: EcommerceBusinessInvestigationApplication = Depends(
        get_business_investigation_application
    ),
) -> BusinessInvestigationSchedulePolicyRevision:
    try:
        return application.get_schedule_policy(_scope(principal), schedule_policy_id)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/schedule-policies/{schedule_policy_id}:update",
    response_model=BusinessInvestigationSchedulePolicyCommandResponse,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationSchedulePolicyUpdate",
)
def update_schedule_policy(
    schedule_policy_id: ResourceIdPath,
    body: PutBusinessInvestigationSchedulePolicyRequest,
    principal: PrincipalDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    case_if_match: str = Header(alias="X-Case-If-Match"),
    application: EcommerceBusinessInvestigationApplication = Depends(
        get_business_investigation_application
    ),
) -> BusinessInvestigationSchedulePolicyCommandResponse:
    try:
        if body.schedule_policy_id != schedule_policy_id:
            raise ValueError("schedulePolicyId must match path")
        return application.put_schedule_policy(
            _scope(principal),
            body.case_ref.resource_id,
            body,
            expected_policy_revision=_expected_version(if_match),
            expected_case_version=_expected_version(case_if_match),
            idempotency_key=_idempotency_key(idempotency_key),
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/schedule-policies/{schedule_policy_id}:trigger",
    response_model=BusinessInvestigationRunCommandResponse,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationSchedulePolicyTrigger",
)
def trigger_schedule_policy(
    schedule_policy_id: ResourceIdPath,
    body: TriggerBusinessInvestigationScheduleRequest,
    principal: PrincipalDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    application: EcommerceBusinessInvestigationApplication = Depends(
        get_business_investigation_application
    ),
) -> BusinessInvestigationRunCommandResponse:
    try:
        return application.trigger_schedule_policy(
            _scope(principal),
            schedule_policy_id,
            body,
            expected_policy_revision=_expected_version(if_match),
            idempotency_key=_idempotency_key(idempotency_key),
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/runs/{run_id}",
    response_model=BusinessInvestigationRunView,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationRunGet",
)
def get_run(
    run_id: ResourceIdPath,
    principal: PrincipalDependency,
    application: EcommerceBusinessInvestigationApplication = Depends(get_business_investigation_application),
) -> BusinessInvestigationRunView:
    try:
        return application.get_run(_scope(principal), run_id)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/runs/{run_id}/view",
    response_model=BusinessInvestigationWorkbenchView,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationRunWorkbenchViewGet",
)
def get_run_view(
    request: Request,
    run_id: ResourceIdPath,
    principal: PrincipalDependency,
    application: EcommerceBusinessInvestigationApplication = Depends(
        get_business_investigation_application
    ),
) -> BusinessInvestigationWorkbenchView:
    try:
        if request.query_params:
            raise ApiError(
                code="BUSINESS_INVESTIGATION_UNKNOWN_QUERY",
                message="Workbench View does not accept query parameters",
                status_code=400,
            )
        return application.get_run_view(
            _scope(principal), run_id, observed_at=datetime.now(UTC)
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/runs/{run_id}/stage-review",
    response_model=BusinessInvestigationStageReviewProjection,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationRunStageReviewGet",
)
def get_run_stage_review(
    request: Request,
    run_id: ResourceIdPath,
    principal: PrincipalDependency,
    application: EcommerceBusinessInvestigationApplication = Depends(
        get_business_investigation_application
    ),
) -> BusinessInvestigationStageReviewProjection:
    try:
        if request.query_params:
            raise ApiError(
                code="BUSINESS_INVESTIGATION_UNKNOWN_QUERY",
                message="Stage Review projection does not accept query parameters",
                status_code=400,
            )
        return application.get_run_stage_review(_scope(principal), run_id)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/runs/{run_id}:review-stage",
    response_model=BusinessInvestigationStageReviewResponse,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationRunStageReview",
)
def review_run_stage(
    run_id: ResourceIdPath,
    body: BusinessInvestigationStageReviewCommand,
    principal: PrincipalDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    application: EcommerceBusinessInvestigationApplication = Depends(
        get_business_investigation_application
    ),
) -> BusinessInvestigationStageReviewResponse:
    try:
        _require_review_write_role(principal)
        return application.review_run_stage(
            _scope(principal),
            run_id,
            body,
            expected_state_version=_expected_version(if_match),
            idempotency_key=_idempotency_key(idempotency_key),
            actor=principal.subject,
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/growth-plans/{plan_id}:approve",
    response_model=GrowthPlanApprovalResponse,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationGrowthPlanApprove",
)
def approve_growth_plan(
    plan_id: ResourceIdPath,
    body: ApproveGrowthPlanRequest,
    principal: PrincipalDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    application: EcommerceBusinessInvestigationApplication = Depends(
        get_business_investigation_application
    ),
) -> GrowthPlanApprovalResponse:
    try:
        _require_review_write_role(principal)
        return application.approve_growth_plan(
            _scope(principal),
            plan_id,
            body,
            expected_version=_expected_version(if_match),
            idempotency_key=_idempotency_key(idempotency_key),
            actor=principal.subject,
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/runs/{run_id}/handoffs:compile",
    response_model=BusinessInvestigationHandoffCompileResponse,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationHandoffCompile",
)
def compile_handoff(
    run_id: ResourceIdPath,
    body: CompileBusinessInvestigationHandoffRequest,
    principal: PrincipalDependency,
    application: EcommerceBusinessInvestigationApplication = Depends(
        get_business_investigation_application
    ),
) -> BusinessInvestigationHandoffCompileResponse:
    try:
        _require_review_write_role(principal)
        return application.compile_handoff(
            _scope(principal),
            run_id,
            body,
            roles=principal.roles,
            principal_markings=principal.markings,
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/runs/{run_id}:request-data",
    response_model=BusinessInvestigationRunStateCommandResponse,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationRunDataRequest",
)
def request_run_data(
    run_id: ResourceIdPath,
    body: RequestBusinessInvestigationDataRequest,
    principal: PrincipalDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    application: EcommerceBusinessInvestigationApplication = Depends(
        get_business_investigation_application
    ),
) -> BusinessInvestigationRunStateCommandResponse:
    try:
        return application.request_run_data(
            _scope(principal),
            run_id,
            body,
            expected_version=_expected_version(if_match),
            idempotency_key=_idempotency_key(idempotency_key),
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/runs/{run_id}:request-missing-data",
    response_model=BusinessInvestigationDataCommandResponse,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationRunMissingDataRequest",
)
def request_run_missing_data(
    run_id: ResourceIdPath,
    body: RequestBusinessInvestigationMissingDataCommand,
    principal: PrincipalDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    application: EcommerceBusinessInvestigationApplication = Depends(
        get_business_investigation_application
    ),
) -> BusinessInvestigationDataCommandResponse:
    try:
        _require_data_write_role(principal)
        return application.request_run_missing_data(
            _scope(principal),
            run_id,
            body,
            expected_version=_expected_version(if_match),
            idempotency_key=_idempotency_key(idempotency_key),
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/runs/{run_id}:confirm-data-requirement",
    response_model=BusinessInvestigationDataCommandResponse,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationRunDataRequirementConfirm",
)
def confirm_run_data_requirement(
    run_id: ResourceIdPath,
    body: ConfirmBusinessInvestigationDataRequirementCommand,
    principal: PrincipalDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    application: EcommerceBusinessInvestigationApplication = Depends(
        get_business_investigation_application
    ),
) -> BusinessInvestigationDataCommandResponse:
    try:
        _require_data_write_role(principal)
        return application.confirm_run_data_requirement(
            _scope(principal),
            run_id,
            body,
            expected_version=_expected_version(if_match),
            idempotency_key=_idempotency_key(idempotency_key),
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except Exception as exc:
        raise _map_error(exc) from exc


def _transition_run(
    run_id: str,
    target: BusinessInvestigationRunControl,
    principal: Principal,
    idempotency_key: str,
    if_match: str,
    application: EcommerceBusinessInvestigationApplication,
) -> BusinessInvestigationRunStateCommandResponse:
    try:
        return application.transition_run_control(
            _scope(principal),
            run_id,
            target,
            expected_version=_expected_version(if_match),
            idempotency_key=_idempotency_key(idempotency_key),
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/runs/{run_id}:pause",
    response_model=BusinessInvestigationRunStateCommandResponse,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationRunPause",
)
def pause_run(
    run_id: ResourceIdPath,
    _body: BusinessInvestigationEmptyCommandRequest,
    principal: PrincipalDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    application: EcommerceBusinessInvestigationApplication = Depends(get_business_investigation_application),
) -> BusinessInvestigationRunStateCommandResponse:
    return _transition_run(
        run_id, BusinessInvestigationRunControl.PAUSED, principal, idempotency_key, if_match, application
    )


@router.post(
    "/runs/{run_id}:resume",
    response_model=BusinessInvestigationRunStateCommandResponse,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationRunResume",
)
def resume_run(
    run_id: ResourceIdPath,
    _body: BusinessInvestigationEmptyCommandRequest,
    principal: PrincipalDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    application: EcommerceBusinessInvestigationApplication = Depends(get_business_investigation_application),
) -> BusinessInvestigationRunStateCommandResponse:
    return _transition_run(
        run_id, BusinessInvestigationRunControl.RUNNING, principal, idempotency_key, if_match, application
    )


@router.post(
    "/runs/{run_id}:cancel",
    response_model=BusinessInvestigationRunStateCommandResponse,
    responses=_ERRORS,
    operation_id="ecommerceInvestigationRunCancel",
)
def cancel_run(
    run_id: ResourceIdPath,
    _body: BusinessInvestigationEmptyCommandRequest,
    principal: PrincipalDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    application: EcommerceBusinessInvestigationApplication = Depends(get_business_investigation_application),
) -> BusinessInvestigationRunStateCommandResponse:
    return _transition_run(
        run_id, BusinessInvestigationRunControl.CANCELLED, principal, idempotency_key, if_match, application
    )


__all__ = ["get_business_investigation_application", "router"]
