"""Canonical tenant-scoped BudgetRevision API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, status

from aos_api.aip_budget_contracts import BudgetRevision, BudgetRevisionCreate
from aos_api.aip_budget_store import (
    AipBudgetAuthorityStore,
    BudgetConflict,
    BudgetIdempotencyConflict,
    BudgetNotFound,
    BudgetStoreError,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope


router = APIRouter(prefix="/v1/aip/budgets", tags=["aip-budgets"])
_STORE = AipBudgetAuthorityStore()


def get_store() -> AipBudgetAuthorityStore:
    return _STORE


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _key(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 120:
        raise ApiError(
            code="AIP_INVALID_ARGUMENT",
            message="Idempotency-Key must be 1..120 characters",
            status_code=400,
        )
    return cleaned


def _version(value: str) -> int:
    cleaned = value.strip().strip('"')
    if not cleaned.isdigit():
        raise ApiError(
            code="AIP_INVALID_ARGUMENT",
            message="If-Match must be an integer authority version",
            status_code=400,
        )
    return int(cleaned)


def _map(exc: BudgetStoreError) -> ApiError:
    if isinstance(exc, BudgetNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, (BudgetConflict, BudgetIdempotencyConflict)):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    return ApiError(code=exc.code, message="budget authority persistence failed", status_code=503)


@router.post("", response_model=BudgetRevision, status_code=status.HTTP_201_CREATED)
def publish_budget(
    body: BudgetRevisionCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    principal: Principal = Depends(require_principal),
    store: AipBudgetAuthorityStore = Depends(get_store),
):
    try:
        return store.publish(
            _scope(principal),
            principal.subject,
            _key(idempotency_key),
            body,
            expected_version=_version(if_match),
        )
    except BudgetStoreError as exc:
        raise _map(exc) from exc


@router.get("/{budget_id}", response_model=BudgetRevision)
def get_budget(
    budget_id: str,
    revision: int | None = Query(default=None, ge=1),
    principal: Principal = Depends(require_principal),
    store: AipBudgetAuthorityStore = Depends(get_store),
):
    try:
        return store.get(_scope(principal), budget_id, revision)
    except BudgetStoreError as exc:
        raise _map(exc) from exc
