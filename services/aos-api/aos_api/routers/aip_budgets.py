"""Canonical tenant-scoped BudgetRevision API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Response, status

from aos_api.aip_budget_contracts import BudgetLifecycle, BudgetRevision, BudgetRevisionCreate
from aos_api.aip_budget_activation_contracts import (
    BudgetActivationDecisionView,
    BudgetActivationPreviewView,
    BudgetActivationRevocationView,
    CreateBudgetActivationPreviewRequest,
    DecideBudgetActivationRequest,
    RevokeBudgetActivationDecisionRequest,
    BudgetPreviewInquiryPending, BudgetPreviewInquiryObserved,
    BudgetDecisionInquiryObserved, BudgetRevocationInquiryObserved,
)
from aos_api.aip_budget_activation_store import (
    AipBudgetActivationStore, BudgetActivationConflict, BudgetActivationDenied, BudgetActivationInquiryUnavailable,
)
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
_ACTIVATION_STORE = AipBudgetActivationStore()


def get_store() -> AipBudgetAuthorityStore:
    return _STORE


def get_activation_store() -> AipBudgetActivationStore:
    return _ACTIVATION_STORE


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


def _map_activation(exc: ValueError) -> ApiError:
    if isinstance(exc, BudgetActivationInquiryUnavailable):
        return ApiError(code=str(exc), message="预算审批暂无法精确对账，请保留原请求", status_code=503)
    if isinstance(exc, BudgetActivationConflict):
        return ApiError(code=str(exc), message="budget activation authority conflict", status_code=409)
    code = str(exc)
    status_code = 403 if "IDENTITY" in code or "MEMBERSHIP" in code else 422
    return ApiError(code=code, message="budget activation authority unavailable", status_code=status_code)


@router.post(
    "/activation-previews", response_model=BudgetActivationPreviewView,
    status_code=status.HTTP_201_CREATED,
)
def create_budget_activation_preview(
    body: CreateBudgetActivationPreviewRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    principal: Principal = Depends(require_principal),
    store: AipBudgetActivationStore = Depends(get_activation_store),
):
    try:
        return store.create_preview(principal, body.target, body.checker_subject,
                                    _key(idempotency_key), expected_head_version=_version(if_match))
    except (BudgetActivationDenied, BudgetActivationConflict) as exc:
        raise _map_activation(exc) from exc


@router.post('/activation-previews/inquiry', response_model=BudgetPreviewInquiryPending | BudgetPreviewInquiryObserved)
def inquire_budget_activation_preview(
    body: CreateBudgetActivationPreviewRequest,
    response: Response,
    idempotency_key: str = Header(alias='Idempotency-Key'),
    if_match: str = Header(alias='If-Match'),
    principal: Principal = Depends(require_principal),
    store: AipBudgetActivationStore = Depends(get_activation_store),
):
    try:
        result = store.inquire_preview(principal, body.target, body.checker_subject,
                                      _key(idempotency_key), expected_head_version=_version(if_match))
    except (BudgetActivationDenied, BudgetActivationConflict) as exc:
        raise _map_activation(exc) from exc
    response.status_code = {'unresolved': 202, 'observed': 200, 'conflict': 409}[result['status']]
    response.headers['Cache-Control'] = 'no-store'
    return result


@router.get("/activation-previews/{preview_id}", response_model=BudgetActivationPreviewView)
def get_budget_activation_preview(
    preview_id: str,
    principal: Principal = Depends(require_principal),
    store: AipBudgetActivationStore = Depends(get_activation_store),
):
    try:
        return store.get_preview(principal, preview_id)
    except (BudgetActivationDenied, BudgetActivationConflict) as exc:
        raise _map_activation(exc) from exc


@router.post(
    "/activation-previews/{preview_id}/decisions",
    response_model=BudgetActivationDecisionView,
    status_code=status.HTTP_201_CREATED,
)
def decide_budget_activation_preview(
    preview_id: str,
    body: DecideBudgetActivationRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    store: AipBudgetActivationStore = Depends(get_activation_store),
):
    try:
        return store.decide(principal, preview_id, _key(idempotency_key),
                            decision=body.decision)
    except (BudgetActivationDenied, BudgetActivationConflict) as exc:
        raise _map_activation(exc) from exc


@router.post(
    "/activation-decisions/{decision_id}/revoke",
    response_model=BudgetActivationRevocationView,
    status_code=status.HTTP_201_CREATED,
)
def revoke_budget_activation_decision(
    decision_id: str,
    body: RevokeBudgetActivationDecisionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    store: AipBudgetActivationStore = Depends(get_activation_store),
):
    try:
        return store.revoke(principal, decision_id, _key(idempotency_key), reason=body.reason)
    except (BudgetActivationDenied, BudgetActivationConflict) as exc:
        raise _map_activation(exc) from exc


@router.post("/activation-previews/{preview_id}/decisions/inquiry",
             response_model=BudgetPreviewInquiryPending | BudgetDecisionInquiryObserved)
def inquire_budget_activation_decision(
    preview_id: str,
    body: DecideBudgetActivationRequest,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    store: AipBudgetActivationStore = Depends(get_activation_store),
):
    try:
        result = store.inquire_decision(principal, preview_id, _key(idempotency_key), decision=body.decision)
    except (BudgetActivationDenied, BudgetActivationConflict) as exc:
        raise _map_activation(exc) from exc
    response.status_code = {"unresolved": 202, "observed": 200, "conflict": 409}[result["status"]]
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/activation-decisions/{decision_id}/revoke/inquiry",
             response_model=BudgetPreviewInquiryPending | BudgetRevocationInquiryObserved)
def inquire_budget_activation_revocation(
    decision_id: str,
    body: RevokeBudgetActivationDecisionRequest,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    store: AipBudgetActivationStore = Depends(get_activation_store),
):
    try:
        result = store.inquire_revocation(principal, decision_id, _key(idempotency_key), reason=body.reason)
    except (BudgetActivationDenied, BudgetActivationConflict) as exc:
        raise _map_activation(exc) from exc
    response.status_code = {"unresolved": 202, "observed": 200, "conflict": 409}[result["status"]]
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("", response_model=BudgetRevision, status_code=status.HTTP_201_CREATED)
def publish_budget(
    body: BudgetRevisionCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    principal: Principal = Depends(require_principal),
    store: AipBudgetAuthorityStore = Depends(get_store),
):
    if body.lifecycle is BudgetLifecycle.ACTIVE:
        raise ApiError(
            code="AIP_BUDGET_ACTIVE_APPROVAL_REQUIRED",
            message="Active budget publication requires a current exact approval authority",
            status_code=422,
        )
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
