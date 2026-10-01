"""Canonical tenant-scoped BudgetRevision API."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, Query, Response, status

from aos_api.aip_budget_contracts import BudgetLifecycle, BudgetRevision, BudgetRevisionCreate
from aos_api.aip_budget_cost_basis import BudgetCostBasisProposal
from aos_api.aip_budget_cost_proposal_store import BudgetCostProposalStore
from aos_api.aip_budget_cost_product import BudgetCostReviewRequest, configured_budget_cost_product, budget_cost_request
from aos_api.aip_budget_consumer_product import (
    BudgetConsumptionRequest, configured_budget_consumer_product, budget_consumption_request,
)
from aos_api.aip_budget_activation_contracts import (
    BudgetActivationDecisionView, BudgetActivationCandidateView, BudgetDecisionReviewView,
    BudgetActivationPreviewView,
    BudgetActivationRevocationView,
    CreateBudgetActivationPreviewRequest,
    DecideBudgetActivationRequest,
    RevokeBudgetActivationDecisionRequest,
    BudgetPreviewInquiryPending, BudgetPreviewInquiryObserved,
    BudgetDecisionInquiryObserved, BudgetRevocationInquiryObserved, BudgetProductInquiryPending,
)
from aos_api.aip_budget_activation_store import (
    AipBudgetActivationStore, BudgetActivationConflict, BudgetActivationDenied, BudgetActivationInquiryUnavailable,
)
from aos_api.aip_budget_activation_product import (
    BudgetProductBlocked, BudgetRequestRef, inquire_request, submit_request,
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
_COST_PROPOSALS = BudgetCostProposalStore()


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


def _cost_call(method, *args):
    try:
        return method(*args)
    except (BudgetActivationDenied, BudgetActivationConflict) as exc:
        raise _map_activation(exc) from exc
    except Exception:
        raise ApiError(code='BUDGET_COST_PERSISTENCE_UNAVAILABLE',
                       message='费用提议暂无法确认，请保留原请求并查询', status_code=503) from None


@router.post('/cost-proposals', status_code=201)
def create_cost_proposal(body: BudgetCostBasisProposal, response: Response,
                         idempotency_key: str = Header(alias='Idempotency-Key'),
                         principal: Principal = Depends(require_principal)) -> dict:
    response.headers['Cache-Control'] = 'no-store'
    return _cost_call(_COST_PROPOSALS.create, principal, body, idempotency_key)


@router.post('/cost-proposals/inquiry')
def inquire_cost_proposal(body: BudgetCostBasisProposal, response: Response,
                          idempotency_key: str = Header(alias='Idempotency-Key'),
                          principal: Principal = Depends(require_principal)) -> dict:
    response.headers['Cache-Control'] = 'no-store'
    result = _cost_call(_COST_PROPOSALS.inquire, principal, body, idempotency_key)
    response.status_code = {'observed': 200, 'unresolved': 202, 'conflict': 409}[result['status']]
    return result


@router.get('/cost-proposals/{proposal_id}')
def get_cost_proposal(proposal_id: str, response: Response,
                      principal: Principal = Depends(require_principal)) -> dict:
    response.headers['Cache-Control'] = 'no-store'
    return _cost_call(_COST_PROPOSALS.get, principal, proposal_id)


@router.get('/cost-proposals/{proposal_id}/review')
def read_cost_review(proposal_id: str, response: Response,
                     principal: Principal = Depends(require_principal)) -> dict:
    response.headers['Cache-Control'] = 'no-store'
    return _cost_call(_COST_PROPOSALS.review, principal, proposal_id)


def _cost_review(response, proposal_id, operation, body, principal, authorization):
    try:
        result = budget_cost_request(configured_budget_cost_product(), proposal_id, operation, body,
                                     principal, authorization)
    except BudgetProductBlocked as exc:
        raise ApiError(code=str(exc), message='费用审核原请求暂无法确认，请保留原引用并查询',
                       status_code=exc.status_code) from None
    except (BudgetActivationDenied, BudgetActivationConflict) as exc:
        raise _map_activation(exc) from None
    response.headers['Cache-Control'] = 'no-store'
    response.status_code = {'observed':200,'not_attempted':200,'unresolved':202,'conflict':409,'blocked':503}[result['status']]
    return result


@router.post('/cost-proposals/{proposal_id}/review-requests/{operation}')
def submit_cost_review(proposal_id: str, operation: str, body: BudgetCostReviewRequest, response: Response,
                       authorization: str = Header(alias='Authorization'),
                       principal: Principal = Depends(require_principal)) -> dict:
    return _cost_review(response, proposal_id, operation, body, principal, authorization)


@router.get('/cost-proposals/{proposal_id}/review-requests/{operation}')
def inquire_cost_review(proposal_id: str, operation: str, response: Response,
                        authorization: str = Header(alias='Authorization'),
                        principal: Principal = Depends(require_principal)) -> dict:
    return _cost_review(response, proposal_id, operation, None, principal, authorization)


def _budget_consumption(response, proposal_id, body, principal, authorization):
    try:
        result = budget_consumption_request(configured_budget_consumer_product(), proposal_id,
                                            body, principal, authorization)
    except BudgetProductBlocked as exc:
        raise ApiError(code=str(exc), message='预算消费原请求暂无法确认，请保留原引用并查询',
                       status_code=exc.status_code) from None
    except (BudgetActivationDenied, BudgetActivationConflict, BudgetActivationInquiryUnavailable) as exc:
        raise _map_activation(exc) from None
    response.headers['Cache-Control'] = 'no-store'
    response.status_code = {'observed':200,'not_attempted':200,'unresolved':202,'conflict':409,'blocked':503}[result['status']]
    return result


@router.post('/cost-proposals/{proposal_id}/consumption-request')
def submit_budget_consumption(proposal_id: str, body: BudgetConsumptionRequest, response: Response,
                              authorization: str = Header(alias='Authorization'),
                              principal: Principal = Depends(require_principal)) -> dict:
    return _budget_consumption(response, proposal_id, body, principal, authorization)


@router.get('/cost-proposals/{proposal_id}/consumption-request')
def inquire_budget_consumption(proposal_id: str, response: Response,
                               authorization: str = Header(alias='Authorization'),
                               principal: Principal = Depends(require_principal)) -> dict:
    return _budget_consumption(response, proposal_id, None, principal, authorization)


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


def _budget_product(response, principal, authorization, ref, body=None):
    try:
        directory = os.environ.get("AOS_BUDGET_REQUEST_DIRECTORY")
        result = (inquire_request(directory, ref, principal, authorization) if body is None else
                  submit_request(directory, ref, body, principal, authorization))
    except BudgetProductBlocked as exc:
        raise ApiError(code=str(exc), message="预算原请求暂无法确认，请保留原引用并只读核对",
                       status_code=exc.status_code) from None
    except (BudgetActivationDenied, BudgetActivationConflict) as exc:
        raise _map_activation(exc) from exc
    response.status_code = {"not_attempted": 200, "observed": 200, "unresolved": 202, "conflict": 409}[result["status"]]
    response.headers["Cache-Control"] = "no-store"
    return result


def _budget_ref(operation, resource_id, revision=None, version=None):
    try:
        return BudgetRequestRef(operation, resource_id, revision, version)
    except BudgetProductBlocked as exc:
        raise ApiError(code=str(exc), message="预算原请求引用无效", status_code=exc.status_code) from None


@router.post("/activation-previews/intent", response_model=BudgetProductInquiryPending | BudgetPreviewInquiryObserved)
def submit_budget_preview_intent(
    body: CreateBudgetActivationPreviewRequest, response: Response,
    if_match: str = Header(alias="If-Match"), authorization: str = Header(alias="Authorization"),
    principal: Principal = Depends(require_principal),
):
    ref = _budget_ref("preview", body.target.budget_id, body.target.revision, _version(if_match))
    return _budget_product(response, principal, authorization, ref, body)


@router.get("/activation-previews/intent", response_model=BudgetProductInquiryPending | BudgetPreviewInquiryObserved)
def inquire_budget_preview_intent(
    response: Response, budget_id: str = Query(alias="budgetId"), revision: int = Query(ge=2),
    head_version: int = Query(alias="headVersion", ge=1),
    authorization: str = Header(alias="Authorization"), principal: Principal = Depends(require_principal),
):
    return _budget_product(response, principal, authorization, _budget_ref("preview", budget_id, revision, head_version))


@router.post("/activation-previews/{preview_id}/decision-intent", response_model=BudgetProductInquiryPending | BudgetDecisionInquiryObserved)
def submit_budget_decision_intent(
    preview_id: str, body: DecideBudgetActivationRequest, response: Response,
    authorization: str = Header(alias="Authorization"), principal: Principal = Depends(require_principal),
):
    return _budget_product(response, principal, authorization, _budget_ref("decision", preview_id), body)


@router.get("/activation-previews/{preview_id}/decision-intent", response_model=BudgetProductInquiryPending | BudgetDecisionInquiryObserved)
def inquire_budget_decision_intent(
    preview_id: str, response: Response,
    authorization: str = Header(alias="Authorization"), principal: Principal = Depends(require_principal),
):
    return _budget_product(response, principal, authorization, _budget_ref("decision", preview_id))


@router.post("/activation-decisions/{decision_id}/revocation-intent", response_model=BudgetProductInquiryPending | BudgetRevocationInquiryObserved)
def submit_budget_revoke_intent(
    decision_id: str, body: RevokeBudgetActivationDecisionRequest, response: Response,
    authorization: str = Header(alias="Authorization"), principal: Principal = Depends(require_principal),
):
    return _budget_product(response, principal, authorization, _budget_ref("revoke", decision_id), body)


@router.get("/activation-decisions/{decision_id}/revocation-intent", response_model=BudgetProductInquiryPending | BudgetRevocationInquiryObserved)
def inquire_budget_revoke_intent(
    decision_id: str, response: Response,
    authorization: str = Header(alias="Authorization"), principal: Principal = Depends(require_principal),
):
    return _budget_product(response, principal, authorization, _budget_ref("revoke", decision_id))


@router.get("/activation-previews/{preview_id}", response_model=BudgetActivationPreviewView)
def get_budget_activation_preview(
    preview_id: str, response: Response,
    principal: Principal = Depends(require_principal),
    store: AipBudgetActivationStore = Depends(get_activation_store),
):
    try:
        result = store.get_preview(principal, preview_id)
        response.headers["Cache-Control"] = "no-store"
        return result
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


@router.get("/activation-candidates/{budget_id}", response_model=BudgetActivationCandidateView)
def get_budget_activation_candidate(
    budget_id: str, response: Response, principal: Principal = Depends(require_principal),
    store: AipBudgetActivationStore = Depends(get_activation_store),
):
    try:
        result = store.get_candidate(principal, budget_id)
    except (BudgetActivationDenied, BudgetActivationConflict) as exc:
        raise _map_activation(exc) from exc
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/activation-decisions/{decision_id}", response_model=BudgetDecisionReviewView)
def get_budget_decision_review(
    decision_id: str, response: Response, principal: Principal = Depends(require_principal),
    store: AipBudgetActivationStore = Depends(get_activation_store),
):
    try:
        result = store.get_decision_review(principal, decision_id)
    except (BudgetActivationDenied, BudgetActivationConflict) as exc:
        raise _map_activation(exc) from exc
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
