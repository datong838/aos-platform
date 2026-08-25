"""W7-08 tenant-scoped media finance authority API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, status

from aos_api.aip_media_finance_contracts import (
    BindMediaUsageRequest,
    MediaFinanceListResponse,
    MediaFinanceSnapshot,
    ObserveMediaCancelRequest,
    PrepareMediaFinanceRequest,
    SettleMediaFinanceRequest,
    TransitionMediaCapacityRequest,
)
from aos_api.aip_media_finance_service import AipMediaFinanceService
from aos_api.aip_media_finance_store import (
    AipMediaFinanceStore,
    MediaFinanceConflict,
    MediaFinanceDependencyBlocked,
    MediaFinanceError,
    MediaFinanceNotFound,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope


router = APIRouter(prefix="/v1/aip/media-finance", tags=["aip-media-finance"])
_STORE = AipMediaFinanceStore()
_SERVICE = AipMediaFinanceService(store=_STORE)
_CONTROL_ROLES = frozenset({"admin", "executor", "aip_executor"})


def get_media_finance_store() -> AipMediaFinanceStore:
    return _STORE


def get_media_finance_service() -> AipMediaFinanceService:
    return _SERVICE


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _control_role(principal: Principal) -> None:
    if not _CONTROL_ROLES.intersection({item.lower() for item in principal.roles}):
        raise ApiError(code="MEDIA_FINANCE_ROLE_REQUIRED", message="trusted media finance role required", status_code=403)


def _map(exc: MediaFinanceError) -> ApiError:
    if isinstance(exc, MediaFinanceNotFound):
        return ApiError(code=exc.code, message="media finance authority not found", status_code=404)
    if isinstance(exc, MediaFinanceConflict):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, MediaFinanceDependencyBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    return ApiError(code=exc.code, message="media finance authority unavailable", status_code=503)


def _command(method: str, finance_id: str, key: str, body, principal: Principal, service: AipMediaFinanceService) -> MediaFinanceSnapshot:
    _control_role(principal)
    try:
        return getattr(service, method)(_scope(principal), principal.subject, finance_id, key, body)
    except MediaFinanceError as exc:
        raise _map(exc) from exc


@router.post("", response_model=MediaFinanceSnapshot, status_code=status.HTTP_201_CREATED)
def prepare_media_finance(body: PrepareMediaFinanceRequest, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), service: AipMediaFinanceService = Depends(get_media_finance_service)) -> MediaFinanceSnapshot:
    _control_role(principal)
    try:
        return service.prepare(_scope(principal), principal.subject, idempotency_key, body)
    except MediaFinanceError as exc:
        raise _map(exc) from exc


@router.get("", response_model=MediaFinanceListResponse)
def list_media_finance(limit: int = Query(default=100, ge=1, le=100), principal: Principal = Depends(require_principal), store: AipMediaFinanceStore = Depends(get_media_finance_store)) -> MediaFinanceListResponse:
    try:
        return store.list(_scope(principal), limit=limit)
    except MediaFinanceError as exc:
        raise _map(exc) from exc


@router.get("/{finance_id}", response_model=MediaFinanceSnapshot)
def get_media_finance(finance_id: str, principal: Principal = Depends(require_principal), store: AipMediaFinanceStore = Depends(get_media_finance_store)) -> MediaFinanceSnapshot:
    try:
        return store.get(_scope(principal), finance_id)
    except MediaFinanceError as exc:
        raise _map(exc) from exc


@router.post("/{finance_id}/capacity-consume", response_model=MediaFinanceSnapshot)
def consume_media_capacity(finance_id: str, body: TransitionMediaCapacityRequest, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), service: AipMediaFinanceService = Depends(get_media_finance_service)) -> MediaFinanceSnapshot:
    return _command("consume_capacity", finance_id, idempotency_key, body, principal, service)


@router.post("/{finance_id}/capacity-release", response_model=MediaFinanceSnapshot)
def release_media_capacity(finance_id: str, body: TransitionMediaCapacityRequest, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), service: AipMediaFinanceService = Depends(get_media_finance_service)) -> MediaFinanceSnapshot:
    return _command("release_capacity", finance_id, idempotency_key, body, principal, service)


@router.post("/{finance_id}/cancel-observations", response_model=MediaFinanceSnapshot)
def observe_media_cancel(finance_id: str, body: ObserveMediaCancelRequest, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), service: AipMediaFinanceService = Depends(get_media_finance_service)) -> MediaFinanceSnapshot:
    return _command("observe_cancel", finance_id, idempotency_key, body, principal, service)


@router.post("/{finance_id}/usage-bindings", response_model=MediaFinanceSnapshot)
def bind_media_usage(finance_id: str, body: BindMediaUsageRequest, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), service: AipMediaFinanceService = Depends(get_media_finance_service)) -> MediaFinanceSnapshot:
    return _command("bind_usage", finance_id, idempotency_key, body, principal, service)


@router.post("/{finance_id}/settlements", response_model=MediaFinanceSnapshot)
def settle_media_finance(finance_id: str, body: SettleMediaFinanceRequest, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), service: AipMediaFinanceService = Depends(get_media_finance_service)) -> MediaFinanceSnapshot:
    return _command("settle", finance_id, idempotency_key, body, principal, service)


__all__ = ["router"]
