"""Tenant-scoped quota and budget-policy authority API."""
from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from starlette.concurrency import run_in_threadpool

from aos_api.aip_budget_policy_renewal_contracts import PolicyIdentifier
from aos_api.aip_budget_policy_renewal_review import (
    BudgetPolicyRenewalReviewReader, BudgetPolicyRenewalReviewSource,
    BudgetPolicyRenewalReviewUnavailable, BudgetPolicyRenewalCheckerDenied,
    BudgetPolicyRenewalCheckerView,
)
from aos_api.aip_budget_policy_renewal_identity import _HUMAN

from aos_api.aip_model_governance_policy_contracts import (
    BudgetPolicyRevision, BudgetPolicyRevisionCreate,
    QuotaPolicyRevision, QuotaPolicyRevisionCreate,
)
from aos_api.aip_model_governance_policy_store import (
    AipModelGovernancePolicyStore, ModelGovernancePolicyConflict,
    ModelGovernancePolicyDependencyBlocked, ModelGovernancePolicyIdempotencyConflict,
    ModelGovernancePolicyNotFound, ModelGovernancePolicyStoreError,
    QuotaPolicyApprovalRequired,
    BudgetPolicyApprovalRequired,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope


router = APIRouter(prefix="/v1/aip/model-governance-policies", tags=["aip-model-governance-policies"])
_STORE = AipModelGovernancePolicyStore()


def get_store() -> AipModelGovernancePolicyStore:
    return _STORE


def get_budget_renewal_review_reader() -> BudgetPolicyRenewalReviewReader:
    return BudgetPolicyRenewalReviewReader()


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _key(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 120:
        raise ApiError(code="AIP_INVALID_ARGUMENT", message="Idempotency-Key must be 1..120 characters", status_code=400)
    return cleaned


def _version(value: str) -> int:
    cleaned = value.strip().strip('"')
    if not cleaned.isdigit():
        raise ApiError(code="AIP_INVALID_ARGUMENT", message="If-Match must be an integer authority version", status_code=400)
    return int(cleaned)


def _map(exc: ModelGovernancePolicyStoreError) -> ApiError:
    if isinstance(exc, ModelGovernancePolicyNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, (ModelGovernancePolicyConflict, ModelGovernancePolicyIdempotencyConflict)):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, ModelGovernancePolicyDependencyBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    if isinstance(exc, QuotaPolicyApprovalRequired):
        return ApiError(code=exc.code, message="当前模型配额策略缺少可核验的正式审批，不能发布为生效状态。", status_code=422)
    if isinstance(exc, BudgetPolicyApprovalRequired):
        return ApiError(code=exc.code, message="当前模型预算策略缺少可核验的正式审批，不能发布为生效状态。", status_code=422)
    return ApiError(code=exc.code, message="model governance policy persistence failed", status_code=503)


def _publish(method, body, key, if_match, principal, store):
    try:
        return getattr(store, method)(_scope(principal), principal.subject, _key(key), body, expected_version=_version(if_match))
    except ModelGovernancePolicyStoreError as exc:
        raise _map(exc) from exc


def _get(method, policy_id, revision, principal, store):
    try:
        return getattr(store, method)(_scope(principal), policy_id, revision)
    except ModelGovernancePolicyStoreError as exc:
        raise _map(exc) from exc


@router.post("/quotas", response_model=QuotaPolicyRevision, status_code=status.HTTP_201_CREATED)
def publish_quota(body: QuotaPolicyRevisionCreate, idempotency_key: str = Header(alias="Idempotency-Key"),
                  if_match: str = Header(alias="If-Match"), principal: Principal = Depends(require_principal),
                  store: AipModelGovernancePolicyStore = Depends(get_store)):
    return _publish("publish_quota", body, idempotency_key, if_match, principal, store)


@router.get("/quotas/{policy_id}", response_model=QuotaPolicyRevision)
def get_quota(policy_id: str, revision: int | None = Query(default=None, ge=1),
              principal: Principal = Depends(require_principal), store: AipModelGovernancePolicyStore = Depends(get_store)):
    return _get("get_quota", policy_id, revision, principal, store)


@router.post("/budgets", response_model=BudgetPolicyRevision, status_code=status.HTTP_201_CREATED)
def publish_budget(body: BudgetPolicyRevisionCreate, idempotency_key: str = Header(alias="Idempotency-Key"),
                   if_match: str = Header(alias="If-Match"), principal: Principal = Depends(require_principal),
                   store: AipModelGovernancePolicyStore = Depends(get_store)):
    return _publish("publish_budget", body, idempotency_key, if_match, principal, store)


@router.get("/budgets/{policy_id}", response_model=BudgetPolicyRevision)
def get_budget(policy_id: str, revision: int | None = Query(default=None, ge=1),
               principal: Principal = Depends(require_principal), store: AipModelGovernancePolicyStore = Depends(get_store)):
    return _get("get_budget", policy_id, revision, principal, store)


@router.get("/budgets/{policy_id}/renewal-source", response_model=BudgetPolicyRenewalReviewSource)
async def get_budget_renewal_source(
    policy_id: PolicyIdentifier, request: Request, response: Response,
    principal: Principal = Depends(require_principal),
    reader: BudgetPolicyRenewalReviewReader = Depends(get_budget_renewal_review_reader),
):
    scope = _scope(principal)
    if scope.key != ("org-org", "dev-project"):
        raise ApiError(code="AIP_BUDGET_RENEWAL_SCOPE_DENIED",
                       message="当前组织与工作区不支持此预算续期审阅。", status_code=403)
    if request.query_params:
        raise ApiError(code="AIP_INVALID_ARGUMENT",
                       message="预算续期源接口不接受查询参数。", status_code=400)
    async for chunk in request.stream():
        if chunk:
            raise ApiError(code="AIP_INVALID_ARGUMENT",
                           message="预算续期源接口不接受请求内容。", status_code=400)
    try:
        result = await run_in_threadpool(reader.read, scope, policy_id)
        response.headers["Cache-Control"] = "no-store"
        return result
    except ModelGovernancePolicyNotFound as exc:
        raise _map(exc) from exc
    except BudgetPolicyRenewalReviewUnavailable as exc:
        raise ApiError(code="AIP_BUDGET_RENEWAL_SOURCE_UNAVAILABLE",
                       message="预算续期来源暂不可核对，请稍后重新读取。", status_code=503) from exc


@router.get("/renewal-checker", response_model=BudgetPolicyRenewalCheckerView)
async def get_budget_renewal_checker(
    request: Request, response: Response, principal: Principal = Depends(require_principal),
    reader: BudgetPolicyRenewalReviewReader = Depends(get_budget_renewal_review_reader),
):
    scope = _scope(principal)
    if principal.token_kind != "oidc" or principal.subject != _HUMAN or scope.key != ("org-org", "dev-project"):
        raise ApiError(code="AIP_BUDGET_RENEWAL_CHECKER_DENIED",
                       message="当前管理员身份不可核对。", status_code=403)
    if request.query_params:
        raise ApiError(code="AIP_INVALID_ARGUMENT", message="身份核验不接受查询参数。", status_code=400)
    async for chunk in request.stream():
        if chunk:
            raise ApiError(code="AIP_INVALID_ARGUMENT", message="身份核验不接受请求内容。", status_code=400)
    try:
        result = await run_in_threadpool(reader.read_checker, scope, principal.subject)
        response.headers["Cache-Control"] = "no-store"
        return result
    except BudgetPolicyRenewalCheckerDenied as exc:
        raise ApiError(code="AIP_BUDGET_RENEWAL_CHECKER_DENIED",
                       message="当前管理员成员资格不可核对。", status_code=403) from exc
    except BudgetPolicyRenewalReviewUnavailable as exc:
        raise ApiError(code="AIP_BUDGET_RENEWAL_SOURCE_UNAVAILABLE",
                       message="管理员身份来源暂不可核对。", status_code=503) from exc
