"""Canonical read-only HTTP adapter for the ecommerce Workshop catalog."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Security
from fastapi.security import HTTPBearer

from aos_api.asset_registry.errors import AssetRegistryError
from aos_api.auth import Principal, require_principal
from aos_api.ecommerce_workshop_catalog import (
    EcommerceWorkshopCatalog,
    build_ecommerce_workshop_catalog,
)
from aos_api.ecommerce_workshop_contracts import (
    EcommerceWorkshopModuleListResponse,
    EcommerceWorkshopModuleReadinessResponse,
)
from aos_api.ecommerce_workshop_operations import EcommerceWorkshopOperations
from aos_api.ecommerce_operation_commands import EcommerceOperationCommands
from aos_api.ecommerce_operation_command_contracts import (
    OperationCommandReadinessEnvelope,
)
from aos_api.ecommerce_operation_command_execution_contracts import (
    ChangeOperationMembershipCommandRequest,
    ClassifyOperationCommandRequest,
    CreateOperationCaseCommandRequest,
    KillOperationAutomationCommandRequest,
    ManageOperationSlaCommandRequest,
    OperationCommandExecutionEnvelope,
)
from aos_api.ecommerce_operation_command_service import (
    CanonicalOperationActionControl,
    EcommerceOperationCommandService,
    OperationCommandConflict,
    OperationCommandDependencyUnavailable,
)
from aos_api.ecommerce_operation_command_observation import (
    EcommerceOperationCommandObservationService,
    OperationCommandObservationConflict,
    OperationCommandObservationEnvelope,
    OperationCommandObservationUnavailable,
    build_operation_observation_control,
)
from aos_api.ecommerce_workshop_operations_contracts import (
    WorkshopOperationsViewEnvelope,
)
from aos_api.ecommerce_workshop_source_readiness import (
    EcommerceWorkshopSourceReadiness,
    SourceReadinessTenantMismatchError,
)
from aos_api.ecommerce_workshop_task_cockpit import (
    EcommerceWorkshopTaskCockpit,
    TaskCockpitPersistenceError,
)
from aos_api.ecommerce_workshop_task_cockpit_contracts import (
    TaskCockpitCheckpointPageEnvelope,
    TaskCockpitCoreEnvelope,
    TaskCockpitStepPageEnvelope,
)
from aos_api.errors import ApiError, ErrorBody
from aos_api.public_contracts import TaskStatus
from aos_api.source_readiness import build_source_readiness_service
from aos_api.source_readiness_contracts import SourceReadinessEnvelope

_bearer = HTTPBearer(auto_error=False)
router = APIRouter(
    prefix="/v1/ecommerce-workshop",
    tags=["ecommerce-workshop"],
    dependencies=[Security(_bearer)],
)
_ERRORS = {
    400: {"model": ErrorBody},
    401: {"model": ErrorBody},
    403: {"model": ErrorBody},
    404: {"model": ErrorBody},
    409: {"model": ErrorBody},
    500: {"model": ErrorBody},
    503: {"model": ErrorBody},
}
PrincipalDependency = Annotated[Principal, Depends(require_principal)]
ModuleIdPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=160,
        pattern=r"^ecommerce[.][a-z0-9]+(?:[.-][a-z0-9]+)*$",
    ),
]
RunIdPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$",
    ),
]
ResultT = TypeVar("ResultT")


@lru_cache(maxsize=1)
def get_ecommerce_workshop_catalog() -> EcommerceWorkshopCatalog:
    return build_ecommerce_workshop_catalog()


@lru_cache(maxsize=1)
def get_ecommerce_workshop_task_cockpit() -> EcommerceWorkshopTaskCockpit:
    return EcommerceWorkshopTaskCockpit()


@lru_cache(maxsize=1)
def get_ecommerce_workshop_source_readiness() -> EcommerceWorkshopSourceReadiness:
    return EcommerceWorkshopSourceReadiness(build_source_readiness_service())


@lru_cache(maxsize=1)
def get_ecommerce_workshop_operations() -> EcommerceWorkshopOperations:
    return EcommerceWorkshopOperations()


@lru_cache(maxsize=1)
def get_ecommerce_operation_commands() -> EcommerceOperationCommands:
    return EcommerceOperationCommands()


@lru_cache(maxsize=1)
def get_ecommerce_operation_command_service() -> EcommerceOperationCommandService:
    return EcommerceOperationCommandService(
        action_control=CanonicalOperationActionControl()
    )


@lru_cache(maxsize=1)
def get_ecommerce_operation_command_observation_service() -> EcommerceOperationCommandObservationService:
    return EcommerceOperationCommandObservationService(
        action_control=build_operation_observation_control()
    )


CatalogDependency = Annotated[
    EcommerceWorkshopCatalog, Depends(get_ecommerce_workshop_catalog)
]
TaskCockpitDependency = Annotated[
    EcommerceWorkshopTaskCockpit, Depends(get_ecommerce_workshop_task_cockpit)
]
SourceReadinessDependency = Annotated[
    EcommerceWorkshopSourceReadiness,
    Depends(get_ecommerce_workshop_source_readiness),
]
OperationsDependency = Annotated[
    EcommerceWorkshopOperations,
    Depends(get_ecommerce_workshop_operations),
]
OperationCommandsDependency = Annotated[
    EcommerceOperationCommands,
    Depends(get_ecommerce_operation_commands),
]
OperationCommandServiceDependency = Annotated[
    EcommerceOperationCommandService,
    Depends(get_ecommerce_operation_command_service),
]
OperationCommandObservationDependency = Annotated[
    EcommerceOperationCommandObservationService,
    Depends(get_ecommerce_operation_command_observation_service),
]


def _operation_command_idempotency(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 200:
        raise ApiError(
            code="ECOMMERCE_OPERATION_COMMAND_INVALID_ARGUMENT",
            message="Idempotency-Key must be 1..200 characters",
            status_code=400,
        )
    return cleaned


def _map_operation_command_error(exc: Exception) -> ApiError:
    if isinstance(exc, OperationCommandConflict):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    return ApiError(
        code=getattr(exc, "code", "ECOMMERCE_OPERATION_COMMAND_ERROR"),
        message=str(exc) or "operation command failed closed",
        status_code=503,
    )


def _reject_query_parameters(request: Request) -> None:
    if request.query_params:
        raise ApiError(
            code="VALIDATION",
            message="ecommerce Workshop reads do not accept query parameters",
            status_code=400,
        )


def _reject_unknown_query_parameters(
    request: Request, *, allowed: frozenset[str]
) -> None:
    unknown = sorted(set(request.query_params) - allowed)
    duplicated = sorted(
        key for key in allowed if len(request.query_params.getlist(key)) > 1
    )
    if unknown or duplicated:
        raise ApiError(
            code="VALIDATION",
            message="unsupported ecommerce Workshop query parameters",
            status_code=400,
            details={"unknown": unknown, "duplicated": duplicated},
        )


def _invoke(operation: Callable[[], ResultT]) -> ResultT:
    try:
        return operation()
    except AssetRegistryError as exc:
        raise ApiError(
            code=exc.code.value,
            message=str(exc),
            status_code=exc.http_status,
            details=exc.details,
        ) from exc


def _require_task_cockpit_installation(
    *, principal: Principal, catalog: EcommerceWorkshopCatalog
) -> None:
    _invoke(
        lambda: catalog.get_readiness(
            module_id="ecommerce.task-cockpit",
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=principal.roles,
            markings=principal.markings,
        )
    )


def _require_operations_installation(
    *, principal: Principal, catalog: EcommerceWorkshopCatalog
) -> None:
    _invoke(
        lambda: catalog.get_readiness(
            module_id="ecommerce.operations",
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=principal.roles,
            markings=principal.markings,
        )
    )


def _require_visible_workshop_installation(
    *, principal: Principal, catalog: EcommerceWorkshopCatalog
) -> None:
    projection = _invoke(
        lambda: catalog.list_modules(
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=principal.roles,
            markings=principal.markings,
        )
    )
    if projection.count == 0:
        raise ApiError(
            code="WORKSHOP_NOT_INSTALLED",
            message="No active ecommerce Workshop module is visible",
            status_code=404,
        )


@router.get(
    "/modules",
    response_model=EcommerceWorkshopModuleListResponse,
    operation_id="ecommerceWorkshopModulesList",
    responses=_ERRORS,
)
def list_ecommerce_workshop_modules(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
) -> EcommerceWorkshopModuleListResponse:
    _reject_query_parameters(request)
    return _invoke(
        lambda: catalog.list_modules(
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=principal.roles,
            markings=principal.markings,
        )
    )


@router.get(
    "/modules/{module_id}/readiness",
    response_model=EcommerceWorkshopModuleReadinessResponse,
    operation_id="ecommerceWorkshopModuleReadinessGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_module_readiness(
    request: Request,
    module_id: ModuleIdPath,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
) -> EcommerceWorkshopModuleReadinessResponse:
    _reject_query_parameters(request)
    return _invoke(
        lambda: catalog.get_readiness(
            module_id=module_id,
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=principal.roles,
            markings=principal.markings,
        )
    )


@router.get(
    "/source-readiness",
    response_model=SourceReadinessEnvelope,
    operation_id="ecommerceWorkshopSourceReadinessGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_source_readiness_envelope(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    source_readiness: SourceReadinessDependency,
) -> SourceReadinessEnvelope:
    _reject_query_parameters(request)
    _require_visible_workshop_installation(principal=principal, catalog=catalog)
    try:
        return source_readiness.read(
            org_id=principal.org_id,
            project_id=principal.project_id,
        )
    except SourceReadinessTenantMismatchError as exc:
        raise ApiError(
            code="SOURCE_READINESS_TENANT_MISMATCH",
            message="SourceReadiness dependency failed closed",
            status_code=500,
        ) from exc


@router.get(
    "/views/operations",
    response_model=WorkshopOperationsViewEnvelope,
    operation_id="ecommerceWorkshopOperationsViewGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_operations_view(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    operations: OperationsDependency,
) -> WorkshopOperationsViewEnvelope:
    _reject_query_parameters(request)
    _require_operations_installation(principal=principal, catalog=catalog)
    return operations.read(
        org_id=principal.org_id,
        project_id=principal.project_id,
    )


@router.get(
    "/commands/operations/readiness",
    response_model=OperationCommandReadinessEnvelope,
    operation_id="ecommerceWorkshopOperationCommandReadinessGet",
    responses=_ERRORS,
)
def get_ecommerce_operation_command_readiness(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    commands: OperationCommandsDependency,
) -> OperationCommandReadinessEnvelope:
    _reject_query_parameters(request)
    _require_operations_installation(principal=principal, catalog=catalog)
    return commands.read_readiness(
        org_id=principal.org_id,
        project_id=principal.project_id,
    )


@router.get(
    "/commands/operations/observations/{proposal_id}/leases/{lease_id}",
    response_model=OperationCommandObservationEnvelope,
    operation_id="ecommerceWorkshopOperationCommandObservationGet",
    responses=_ERRORS,
)
def get_ecommerce_operation_command_observation(
    request: Request,
    proposal_id: Annotated[str, Path(min_length=1, max_length=300)],
    lease_id: Annotated[str, Path(min_length=1, max_length=300)],
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    observations: OperationCommandObservationDependency,
) -> OperationCommandObservationEnvelope:
    _reject_query_parameters(request)
    _require_operations_installation(principal=principal, catalog=catalog)
    try:
        return observations.read(principal, proposal_id, lease_id)
    except OperationCommandObservationConflict as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=409) from exc
    except OperationCommandObservationUnavailable as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=503) from exc


@router.post(
    "/commands/operations/classify",
    response_model=OperationCommandExecutionEnvelope,
    operation_id="ecommerceWorkshopOperationClassifyPost",
    responses=_ERRORS,
)
def classify_ecommerce_operation_event(
    body: ClassifyOperationCommandRequest,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: OperationCommandServiceDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> OperationCommandExecutionEnvelope:
    _require_operations_installation(principal=principal, catalog=catalog)
    try:
        return service.classify(
            principal, _operation_command_idempotency(idempotency_key), body
        )
    except (OperationCommandConflict, OperationCommandDependencyUnavailable) as exc:
        raise _map_operation_command_error(exc) from exc


@router.post(
    "/commands/operations/create-case",
    response_model=OperationCommandExecutionEnvelope,
    operation_id="ecommerceWorkshopOperationCreateCasePost",
    responses=_ERRORS,
)
def create_ecommerce_operation_case(
    body: CreateOperationCaseCommandRequest,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: OperationCommandServiceDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> OperationCommandExecutionEnvelope:
    _require_operations_installation(principal=principal, catalog=catalog)
    try:
        return service.create_case(
            principal, _operation_command_idempotency(idempotency_key), body
        )
    except (OperationCommandConflict, OperationCommandDependencyUnavailable) as exc:
        raise _map_operation_command_error(exc) from exc


@router.post(
    "/commands/operations/change-membership",
    response_model=OperationCommandExecutionEnvelope,
    operation_id="ecommerceWorkshopOperationChangeMembershipPost",
    responses=_ERRORS,
)
def change_ecommerce_operation_membership(
    body: ChangeOperationMembershipCommandRequest,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: OperationCommandServiceDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> OperationCommandExecutionEnvelope:
    _require_operations_installation(principal=principal, catalog=catalog)
    try:
        return service.change_membership(
            principal, _operation_command_idempotency(idempotency_key), body
        )
    except (OperationCommandConflict, OperationCommandDependencyUnavailable) as exc:
        raise _map_operation_command_error(exc) from exc


@router.post(
    "/commands/operations/manage-sla",
    response_model=OperationCommandExecutionEnvelope,
    operation_id="ecommerceWorkshopOperationManageSlaPost",
    responses=_ERRORS,
)
def manage_ecommerce_operation_sla(
    body: ManageOperationSlaCommandRequest,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: OperationCommandServiceDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> OperationCommandExecutionEnvelope:
    _require_operations_installation(principal=principal, catalog=catalog)
    try:
        return service.manage_sla(
            principal, _operation_command_idempotency(idempotency_key), body
        )
    except (OperationCommandConflict, OperationCommandDependencyUnavailable) as exc:
        raise _map_operation_command_error(exc) from exc


@router.post(
    "/commands/operations/automation-kill",
    response_model=OperationCommandExecutionEnvelope,
    operation_id="ecommerceWorkshopOperationAutomationKillPost",
    responses=_ERRORS,
)
def kill_ecommerce_operation_automation(
    body: KillOperationAutomationCommandRequest,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    service: OperationCommandServiceDependency,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> OperationCommandExecutionEnvelope:
    _require_operations_installation(principal=principal, catalog=catalog)
    try:
        return service.automation_kill(
            principal, _operation_command_idempotency(idempotency_key), body
        )
    except (OperationCommandConflict, OperationCommandDependencyUnavailable) as exc:
        raise _map_operation_command_error(exc) from exc


@router.get(
    "/views/task-cockpit",
    response_model=TaskCockpitCoreEnvelope,
    operation_id="ecommerceWorkshopTaskCockpitCoreGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_task_cockpit_core(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    cockpit: TaskCockpitDependency,
    status: Annotated[TaskStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1, max_length=4096)] = None,
) -> TaskCockpitCoreEnvelope:
    _reject_unknown_query_parameters(
        request, allowed=frozenset({"status", "limit", "cursor"})
    )
    _require_task_cockpit_installation(
        principal=principal,
        catalog=catalog,
    )
    try:
        return cockpit.read_core(
            org_id=principal.org_id,
            project_id=principal.project_id,
            status=status,
            limit=limit,
            cursor=cursor,
        )
    except TaskCockpitPersistenceError as exc:
        raise ApiError(
            code="TASK_COCKPIT_DEPENDENCY_UNAVAILABLE",
            message="Task Cockpit read dependency is unavailable",
            status_code=503,
        ) from exc


@router.get(
    "/views/task-cockpit/runs/{run_id}/steps",
    response_model=TaskCockpitStepPageEnvelope,
    operation_id="ecommerceWorkshopTaskCockpitRunStepsList",
    responses=_ERRORS,
)
def list_ecommerce_workshop_task_cockpit_run_steps(
    request: Request,
    run_id: RunIdPath,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    cockpit: TaskCockpitDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1, max_length=4096)] = None,
) -> TaskCockpitStepPageEnvelope:
    _reject_unknown_query_parameters(
        request, allowed=frozenset({"limit", "cursor"})
    )
    _require_task_cockpit_installation(principal=principal, catalog=catalog)
    try:
        return cockpit.read_steps(
            org_id=principal.org_id,
            project_id=principal.project_id,
            run_id=run_id,
            limit=limit,
            cursor=cursor,
        )
    except TaskCockpitPersistenceError as exc:
        raise ApiError(
            code="TASK_COCKPIT_DEPENDENCY_UNAVAILABLE",
            message="Task Cockpit read dependency is unavailable",
            status_code=503,
        ) from exc


@router.get(
    "/views/task-cockpit/runs/{run_id}/checkpoints",
    response_model=TaskCockpitCheckpointPageEnvelope,
    operation_id="ecommerceWorkshopTaskCockpitRunCheckpointsList",
    responses=_ERRORS,
)
def list_ecommerce_workshop_task_cockpit_run_checkpoints(
    request: Request,
    run_id: RunIdPath,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
    cockpit: TaskCockpitDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1, max_length=4096)] = None,
) -> TaskCockpitCheckpointPageEnvelope:
    _reject_unknown_query_parameters(
        request, allowed=frozenset({"limit", "cursor"})
    )
    _require_task_cockpit_installation(principal=principal, catalog=catalog)
    try:
        return cockpit.read_checkpoints(
            org_id=principal.org_id,
            project_id=principal.project_id,
            run_id=run_id,
            limit=limit,
            cursor=cursor,
        )
    except TaskCockpitPersistenceError as exc:
        raise ApiError(
            code="TASK_COCKPIT_DEPENDENCY_UNAVAILABLE",
            message="Task Cockpit read dependency is unavailable",
            status_code=503,
        ) from exc
