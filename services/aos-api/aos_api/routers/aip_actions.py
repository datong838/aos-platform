"""Canonical AIP-3 Action Proposal, Draft and Approval API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, status

from aos_api.aip_action_models import (
    AcquireExecutionLeaseRequest,
    ActionDraftBundle,
    ActionDraftRevisionSnapshot,
    ActionExecutionView,
    ActionProposalListResponse,
    ActionProposalTimeline,
    CreateCompensationRequest,
    CreateActionDraftRequest,
    CreateActionProposalRequest,
    DecideActionProposalRequest,
    ExecuteActionLeaseRequest,
    ReconcileActionReceiptRequest,
    ReviseActionDraftRequest,
    SubmitActionDraftRequest,
)
from aos_api.aip_action_adapters import ACTION_ADAPTERS
from aos_api.aip_action_execution import (
    AipActionBudgetExceeded,
    AipActionDependencyUnavailable,
    AipActionExecutionService,
    AipActionForbidden,
)
from aos_api.aip_action_service import AipActionService
from aos_api.aip_action_store import (
    AipActionConflict,
    AipActionIdempotencyConflict,
    AipActionNotFound,
    AipActionStore,
    AipActionStoreError,
    AipActionTransitionBlocked,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip", tags=["aip-actions"])
_STORE = AipActionStore()


def get_aip_action_store() -> AipActionStore:
    return _STORE


def get_aip_action_service(store: AipActionStore = Depends(get_aip_action_store)) -> AipActionService:
    return AipActionService(store)


def get_aip_action_execution_service(
    store: AipActionStore = Depends(get_aip_action_store),
) -> AipActionExecutionService:
    return AipActionExecutionService(store, ACTION_ADAPTERS)


def _idem(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 200:
        raise ApiError(code="AIP_INVALID_ARGUMENT", message="Idempotency-Key must be 1..200 characters", status_code=400)
    return cleaned


def _map_error(exc: AipActionStoreError) -> ApiError:
    if isinstance(exc, AipActionForbidden):
        return ApiError(code=exc.code, message=str(exc), status_code=403)
    if isinstance(exc, AipActionBudgetExceeded):
        return ApiError(code=exc.code, message=str(exc), status_code=429)
    if isinstance(exc, AipActionDependencyUnavailable):
        return ApiError(code=exc.code, message=str(exc), status_code=503)
    if isinstance(exc, AipActionNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, (AipActionConflict, AipActionIdempotencyConflict)):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, AipActionTransitionBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    return ApiError(code=exc.code, message="action control persistence failed", status_code=503)


@router.post("/action-proposals", response_model=ActionDraftBundle, status_code=status.HTTP_201_CREATED)
def create_action_proposal(
    body: CreateActionProposalRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipActionService = Depends(get_aip_action_service),
) -> ActionDraftBundle:
    try:
        return service.create_proposal(principal, _idem(idempotency_key), body)
    except AipActionStoreError as exc:
        raise _map_error(exc) from exc


@router.post(
    "/action-drafts",
    response_model=ActionDraftRevisionSnapshot,
    status_code=status.HTTP_201_CREATED,
)
def create_action_draft(
    body: CreateActionDraftRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipActionService = Depends(get_aip_action_service),
) -> ActionDraftRevisionSnapshot:
    try:
        return service.create_draft(principal, _idem(idempotency_key), body)
    except AipActionStoreError as exc:
        raise _map_error(exc) from exc


@router.post(
    "/action-drafts/{draft_id}/revisions",
    response_model=ActionDraftRevisionSnapshot,
)
def revise_action_draft(
    draft_id: str,
    body: ReviseActionDraftRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipActionService = Depends(get_aip_action_service),
) -> ActionDraftRevisionSnapshot:
    try:
        return service.revise_draft(
            principal, draft_id, _idem(idempotency_key), body
        )
    except AipActionStoreError as exc:
        raise _map_error(exc) from exc


@router.post(
    "/action-drafts/{draft_id}/submit",
    response_model=ActionDraftBundle,
    status_code=status.HTTP_201_CREATED,
)
def submit_action_draft(
    draft_id: str,
    body: SubmitActionDraftRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipActionService = Depends(get_aip_action_service),
) -> ActionDraftBundle:
    try:
        return service.submit_draft(
            principal, draft_id, _idem(idempotency_key), body
        )
    except AipActionStoreError as exc:
        raise _map_error(exc) from exc


@router.get("/action-proposals", response_model=ActionProposalListResponse)
def list_action_proposals(
    limit: int = Query(default=100, ge=1, le=500),
    principal: Principal = Depends(require_principal),
    store: AipActionStore = Depends(get_aip_action_store),
) -> ActionProposalListResponse:
    try:
        items = store.list_proposals(TenantScope(principal.org_id, principal.project_id), limit)
    except AipActionStoreError as exc:
        raise _map_error(exc) from exc
    return ActionProposalListResponse(items=items, count=len(items))


@router.get("/action-proposals/{proposal_id}", response_model=ActionDraftBundle)
def get_action_proposal(
    proposal_id: str,
    principal: Principal = Depends(require_principal),
    store: AipActionStore = Depends(get_aip_action_store),
) -> ActionDraftBundle:
    try:
        return store.get_proposal(TenantScope(principal.org_id, principal.project_id), proposal_id)
    except AipActionStoreError as exc:
        raise _map_error(exc) from exc


@router.post("/action-proposals/{proposal_id}/decision", response_model=ActionDraftBundle)
def decide_action_proposal(
    proposal_id: str,
    body: DecideActionProposalRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipActionService = Depends(get_aip_action_service),
) -> ActionDraftBundle:
    try:
        return service.decide(principal, proposal_id, _idem(idempotency_key), body)
    except AipActionStoreError as exc:
        raise _map_error(exc) from exc


@router.post("/action-proposals/{proposal_id}/lease", response_model=ActionExecutionView)
def acquire_action_execution_lease(
    proposal_id: str,
    body: AcquireExecutionLeaseRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipActionExecutionService = Depends(get_aip_action_execution_service),
) -> ActionExecutionView:
    try:
        return service.acquire_lease(principal, proposal_id, _idem(idempotency_key), body)
    except AipActionStoreError as exc:
        raise _map_error(exc) from exc


@router.post("/action-leases/{lease_id}/execute", response_model=ActionExecutionView)
def execute_action_lease(
    lease_id: str,
    body: ExecuteActionLeaseRequest,
    principal: Principal = Depends(require_principal),
    service: AipActionExecutionService = Depends(get_aip_action_execution_service),
) -> ActionExecutionView:
    try:
        return service.execute(principal, lease_id, body.expected_proposal_hash)
    except AipActionStoreError as exc:
        raise _map_error(exc) from exc


@router.post("/action-receipts/{receipt_id}/reconcile", response_model=ActionExecutionView)
def reconcile_action_receipt(
    receipt_id: str,
    body: ReconcileActionReceiptRequest,
    principal: Principal = Depends(require_principal),
    service: AipActionExecutionService = Depends(get_aip_action_execution_service),
) -> ActionExecutionView:
    try:
        return service.reconcile(principal, receipt_id, body.reason)
    except AipActionStoreError as exc:
        raise _map_error(exc) from exc


@router.post("/action-proposals/{proposal_id}/compensation", response_model=ActionDraftBundle, status_code=status.HTTP_201_CREATED)
def create_action_compensation(
    proposal_id: str,
    body: CreateCompensationRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipActionExecutionService = Depends(get_aip_action_execution_service),
) -> ActionDraftBundle:
    try:
        return service.create_compensation(principal, proposal_id, _idem(idempotency_key), body)
    except AipActionStoreError as exc:
        raise _map_error(exc) from exc


@router.get("/action-proposals/{proposal_id}/execution", response_model=ActionExecutionView)
def get_action_execution_view(
    proposal_id: str,
    principal: Principal = Depends(require_principal),
    service: AipActionExecutionService = Depends(get_aip_action_execution_service),
) -> ActionExecutionView:
    try:
        return service.get_execution_view(principal, proposal_id)
    except AipActionStoreError as exc:
        raise _map_error(exc) from exc


@router.get("/action-proposals/{proposal_id}/timeline", response_model=ActionProposalTimeline)
def get_action_proposal_timeline(
    proposal_id: str,
    principal: Principal = Depends(require_principal),
    store: AipActionStore = Depends(get_aip_action_store),
) -> ActionProposalTimeline:
    try:
        return store.timeline(TenantScope(principal.org_id, principal.project_id), proposal_id)
    except AipActionStoreError as exc:
        raise _map_error(exc) from exc
