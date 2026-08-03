"""Canonical HTTP adapter for M4 Integration Cases and Evidence snapshots."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Collection, Mapping
from functools import lru_cache
from typing import Annotated, Any, Protocol, TypeVar, cast

from fastapi import APIRouter, Depends, Path, Query, Request, Response, Security, status
from fastapi.security import HTTPBearer

from aos_api.asset_registry.errors import (
    AssetRegistryError,
    AssetRegistryErrorCode,
)
from aos_api.asset_registry.integration_contracts import (
    INTEGRATION_CASE_DETAIL_ADAPTER,
    MAX_CASE_LIST_LIMIT,
    MAX_CASE_LIST_OFFSET,
    MAX_TIMELINE_ITEMS,
    CreateIntegrationCaseRequest,
    CreateIntegrationEvidenceSnapshotRequest,
    IntegrationCaseDetail,
    IntegrationCaseListResponse,
    IntegrationCaseScope,
    IntegrationCaseTimelineResponse,
    IntegrationEvidenceSnapshotResponse,
)
from aos_api.asset_registry.integration_policy import (
    CREATE_CASE_OPERATION,
    GET_CASE_OPERATION,
    LIST_CASES_OPERATION,
    LIST_TIMELINE_OPERATION,
    PROJECT_CASE_OPERATION,
    require_integration_case_role,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError, ErrorBody
from aos_api.routers.asset_control_headers import (
    require_idempotency_key,
    require_if_match,
)


class IntegrationRequestContextValue(Protocol):
    """Structural view of the Service-owned verified request context."""

    org_id: str
    project_id: str
    subject: str
    roles: Collection[str]
    markings: Collection[str]


class IntegrationCommandReceipt(Protocol):
    status_code: int
    response_json: Mapping[str, Any]
    response_etag: str


class IntegrationCaseControl(Protocol):
    def list_cases(
        self,
        *,
        context: IntegrationRequestContextValue,
        scope: IntegrationCaseScope,
        limit: int,
        offset: int,
    ) -> IntegrationCaseListResponse: ...

    def create_case(
        self,
        *,
        context: IntegrationRequestContextValue,
        request: CreateIntegrationCaseRequest,
        idempotency_key: str,
    ) -> IntegrationCommandReceipt: ...

    def get_case(
        self,
        *,
        context: IntegrationRequestContextValue,
        case_id: str,
    ) -> IntegrationCaseDetail: ...

    def create_evidence_snapshot(
        self,
        *,
        context: IntegrationRequestContextValue,
        case_id: str,
        request: CreateIntegrationEvidenceSnapshotRequest,
        idempotency_key: str,
        if_match: str,
    ) -> IntegrationCommandReceipt: ...

    def list_timeline(
        self,
        *,
        context: IntegrationRequestContextValue,
        case_id: str,
        limit: int,
        offset: int,
    ) -> IntegrationCaseTimelineResponse: ...


class IntegrationCaseServiceFactory(Protocol):
    def __call__(self) -> IntegrationCaseControl: ...


def build_integration_case_service() -> IntegrationCaseControl:
    """Lazily call the production wiring hook installed by the integrator."""

    from aos_api.asset_registry.control_wiring import (  # type: ignore[attr-defined]
        build_integration_case_service as factory,
    )

    return cast(IntegrationCaseControl, factory())


@lru_cache(maxsize=1)
def get_integration_case_service() -> IntegrationCaseControl:
    return build_integration_case_service()


_bearer = HTTPBearer(auto_error=False)
router = APIRouter(
    prefix="/v1/integration-cases",
    tags=["asset-control"],
    dependencies=[Security(_bearer)],
)

_BASE_ERRORS = {
    400: {"model": ErrorBody},
    401: {"model": ErrorBody},
    403: {"model": ErrorBody},
    404: {"model": ErrorBody},
    422: {"model": ErrorBody},
    500: {"model": ErrorBody},
}
_COMMAND_ERRORS = {**_BASE_ERRORS, 409: {"model": ErrorBody}}
_SNAPSHOT_ERRORS = {**_COMMAND_ERRORS, 428: {"model": ErrorBody}}
_IDEMPOTENCY_PARAMETER = {
    "name": "Idempotency-Key",
    "in": "header",
    "required": True,
    "schema": {"type": "string", "minLength": 1, "maxLength": 160},
}
_IF_MATCH_PARAMETER = {
    "name": "If-Match",
    "in": "header",
    "required": True,
    "schema": {"type": "string", "pattern": '^"[1-9][0-9]*"$'},
}
_ETAG_HEADER = {
    "ETag": {
        "description": "Strong Integration Case instance revision validator.",
        "schema": {"type": "string"},
    }
}
_STRONG_ETAG = re.compile(r'^"[1-9][0-9]*"$')

ResultT = TypeVar("ResultT")
PrincipalDependency = Annotated[Principal, Depends(require_principal)]
IntegrationCaseServiceDependency = Annotated[
    IntegrationCaseControl, Depends(get_integration_case_service)
]
CanonicalUuidPath = Annotated[
    str,
    Path(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    ),
]
CaseListLimitQuery = Annotated[int, Query(ge=1, le=MAX_CASE_LIST_LIMIT)]
TimelineLimitQuery = Annotated[int, Query(ge=1, le=MAX_TIMELINE_ITEMS)]
ListOffsetQuery = Annotated[int, Query(ge=0, le=MAX_CASE_LIST_OFFSET)]


def build_integration_request_context(
    principal: Principal,
) -> IntegrationRequestContextValue:
    """Lazily construct the context type owned by the M4-2 Service worker."""

    from aos_api.asset_registry.integration_service import (  # type: ignore[import-not-found]
        IntegrationRequestContext,
    )

    return cast(
        IntegrationRequestContextValue,
        IntegrationRequestContext(
            org_id=principal.org_id,
            project_id=principal.project_id,
            subject=principal.subject,
            roles=tuple(principal.roles),
            markings=tuple(principal.markings),
        ),
    )


def _context(principal: Principal) -> IntegrationRequestContextValue:
    return build_integration_request_context(principal)


def _invoke(operation: Callable[[], ResultT], *, conceal_not_visible: bool = False) -> ResultT:
    try:
        return operation()
    except AssetRegistryError as exc:
        if conceal_not_visible and exc.code in {
            AssetRegistryErrorCode.MARKING_ACCESS_DENIED,
            AssetRegistryErrorCode.NOT_FOUND,
        }:
            raise ApiError(
                code=AssetRegistryErrorCode.NOT_FOUND.value,
                message="integration case resource not found",
                status_code=404,
                details=None,
            ) from exc
        raise ApiError(
            code=exc.code.value,
            message=str(exc),
            status_code=exc.http_status,
            details=exc.details,
        ) from exc


def _authorize(principal: Principal, operation: str) -> None:
    _invoke(lambda: require_integration_case_role(roles=principal.roles, operation=operation))


def _strict_query(
    request: Request,
    *,
    allowed: Collection[str],
    required: Collection[str] = (),
) -> None:
    names = [name for name, _value in request.query_params.multi_items()]
    allowed_names = set(allowed)
    required_names = set(required)
    if any(name not in allowed_names for name in names):
        raise ApiError(code="VALIDATION", message="unknown query parameter", status_code=400)
    if len(names) != len(set(names)):
        raise ApiError(code="VALIDATION", message="duplicate query parameter", status_code=400)
    if not required_names.issubset(names):
        raise ApiError(code="VALIDATION", message="required query parameter missing", status_code=400)


def _receipt_payload(
    receipt: IntegrationCommandReceipt,
    response: Response,
    *,
    expected_status: int,
    snapshot: bool,
) -> IntegrationCaseDetail | IntegrationEvidenceSnapshotResponse:
    try:
        if receipt.status_code != expected_status:
            raise ValueError("command receipt status is invalid")
        payload = dict(receipt.response_json)
        payload_json = json.dumps(payload)
        parsed: IntegrationCaseDetail | IntegrationEvidenceSnapshotResponse
        if snapshot:
            parsed = IntegrationEvidenceSnapshotResponse.model_validate_json(payload_json)
        else:
            parsed = INTEGRATION_CASE_DETAIL_ADAPTER.validate_json(payload_json)
            if parsed.scope != IntegrationCaseScope.CURRENT:
                raise ValueError("create response must be a current case")
        expected_etag = f'"{parsed.etag_version}"'
        if (
            _STRONG_ETAG.fullmatch(receipt.response_etag) is None
            or receipt.response_etag != expected_etag
        ):
            raise ValueError("command receipt ETag is inconsistent")
    except (TypeError, ValueError) as exc:
        raise ApiError(
            code=AssetRegistryErrorCode.EVIDENCE_INTEGRITY_CORRUPT.value,
            message="integration command receipt failed integrity verification",
            status_code=500,
        ) from exc
    response.headers["ETag"] = receipt.response_etag
    return parsed


@router.get(
    "",
    response_model=IntegrationCaseListResponse,
    operation_id="list_integration_cases",
    responses=_BASE_ERRORS,
)
def list_integration_cases(
    request: Request,
    principal: PrincipalDependency,
    service: IntegrationCaseServiceDependency,
    scope: Annotated[IntegrationCaseScope, Query()],
    limit: CaseListLimitQuery = 50,
    offset: ListOffsetQuery = 0,
) -> IntegrationCaseListResponse:
    _strict_query(request, allowed={"scope", "limit", "offset"}, required={"scope"})
    _authorize(principal, LIST_CASES_OPERATION)
    return _invoke(
        lambda: service.list_cases(
            context=_context(principal),
            scope=scope,
            limit=limit,
            offset=offset,
        )
    )


@router.post(
    "",
    response_model=IntegrationCaseDetail,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_integration_case",
    responses={201: {"headers": _ETAG_HEADER}, **_COMMAND_ERRORS},
    openapi_extra={"parameters": [_IDEMPOTENCY_PARAMETER]},
)
def create_integration_case(
    body: CreateIntegrationCaseRequest,
    request: Request,
    response: Response,
    principal: PrincipalDependency,
    service: IntegrationCaseServiceDependency,
) -> IntegrationCaseDetail:
    _strict_query(request, allowed=set())
    _authorize(principal, CREATE_CASE_OPERATION)
    key = _invoke(lambda: require_idempotency_key(request))
    receipt = _invoke(
        lambda: service.create_case(
            context=_context(principal),
            request=body,
            idempotency_key=key,
        )
    )
    return cast(
        IntegrationCaseDetail,
        _receipt_payload(receipt, response, expected_status=201, snapshot=False),
    )


@router.get(
    "/{case_id}",
    response_model=IntegrationCaseDetail,
    operation_id="get_integration_case",
    responses={200: {"headers": _ETAG_HEADER}, **_BASE_ERRORS},
)
def get_integration_case(
    case_id: CanonicalUuidPath,
    request: Request,
    response: Response,
    principal: PrincipalDependency,
    service: IntegrationCaseServiceDependency,
) -> IntegrationCaseDetail:
    _strict_query(request, allowed=set())
    _authorize(principal, GET_CASE_OPERATION)
    result = _invoke(
        lambda: service.get_case(context=_context(principal), case_id=case_id),
        conceal_not_visible=True,
    )
    response.headers["ETag"] = f'"{result.etag_version}"'
    return result


@router.post(
    "/{case_id}/evidence-snapshots",
    response_model=IntegrationEvidenceSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_integration_evidence_snapshot",
    responses={201: {"headers": _ETAG_HEADER}, **_SNAPSHOT_ERRORS},
    openapi_extra={"parameters": [_IDEMPOTENCY_PARAMETER, _IF_MATCH_PARAMETER]},
)
def create_integration_evidence_snapshot(
    case_id: CanonicalUuidPath,
    body: CreateIntegrationEvidenceSnapshotRequest,
    request: Request,
    response: Response,
    principal: PrincipalDependency,
    service: IntegrationCaseServiceDependency,
) -> IntegrationEvidenceSnapshotResponse:
    _strict_query(request, allowed=set())
    _authorize(principal, PROJECT_CASE_OPERATION)
    key = _invoke(lambda: require_idempotency_key(request))
    if_match = _invoke(lambda: require_if_match(request))
    receipt = _invoke(
        lambda: service.create_evidence_snapshot(
            context=_context(principal),
            case_id=case_id,
            request=body,
            idempotency_key=key,
            if_match=if_match,
        )
    )
    return cast(
        IntegrationEvidenceSnapshotResponse,
        _receipt_payload(receipt, response, expected_status=201, snapshot=True),
    )


@router.get(
    "/{case_id}/timeline",
    response_model=IntegrationCaseTimelineResponse,
    operation_id="list_integration_case_timeline",
    responses=_BASE_ERRORS,
)
def list_integration_case_timeline(
    case_id: CanonicalUuidPath,
    request: Request,
    principal: PrincipalDependency,
    service: IntegrationCaseServiceDependency,
    limit: TimelineLimitQuery = 50,
    offset: ListOffsetQuery = 0,
) -> IntegrationCaseTimelineResponse:
    _strict_query(request, allowed={"limit", "offset"})
    _authorize(principal, LIST_TIMELINE_OPERATION)
    return _invoke(
        lambda: service.list_timeline(
            context=_context(principal),
            case_id=case_id,
            limit=limit,
            offset=offset,
        ),
        conceal_not_visible=True,
    )
