"""Canonical tenant-scoped runtime egress and data-classification policies."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, status

from aos_api.aip_runtime_guard_policy_contracts import (
    DataClassificationPolicyRevision,
    DataClassificationPolicyRevisionCreate,
    EgressPolicyRevision,
    EgressPolicyRevisionCreate,
)
from aos_api.aip_runtime_guard_policy_store import (
    AipRuntimeGuardPolicyStore,
    GuardPolicyConflict,
    GuardPolicyDependencyBlocked,
    GuardPolicyIdempotencyConflict,
    GuardPolicyNotFound,
    GuardPolicyStoreError,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope


router = APIRouter(prefix="/v1/aip/runtime-guard-policies", tags=["aip-runtime-guard-policies"])
_STORE = AipRuntimeGuardPolicyStore()


def get_store() -> AipRuntimeGuardPolicyStore:
    return _STORE


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


def _map(exc: GuardPolicyStoreError) -> ApiError:
    if isinstance(exc, GuardPolicyNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, (GuardPolicyConflict, GuardPolicyIdempotencyConflict)):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, GuardPolicyDependencyBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    return ApiError(code=exc.code, message="runtime guard policy persistence failed", status_code=503)


def _publish(method: str, body, key: str, if_match: str, principal: Principal, store: AipRuntimeGuardPolicyStore):
    try:
        return getattr(store, method)(
            _scope(principal),
            principal.subject,
            _key(key),
            body,
            expected_version=_version(if_match),
        )
    except GuardPolicyStoreError as exc:
        raise _map(exc) from exc


def _get(method: str, policy_id: str, revision: int | None, principal: Principal, store: AipRuntimeGuardPolicyStore):
    try:
        return getattr(store, method)(_scope(principal), policy_id, revision)
    except GuardPolicyStoreError as exc:
        raise _map(exc) from exc


@router.post("/egress", response_model=EgressPolicyRevision, status_code=status.HTTP_201_CREATED)
def publish_egress(
    body: EgressPolicyRevisionCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    principal: Principal = Depends(require_principal),
    store: AipRuntimeGuardPolicyStore = Depends(get_store),
):
    return _publish("publish_egress", body, idempotency_key, if_match, principal, store)


@router.get("/egress/{policy_id}", response_model=EgressPolicyRevision)
def get_egress(
    policy_id: str,
    revision: int | None = Query(default=None, ge=1),
    principal: Principal = Depends(require_principal),
    store: AipRuntimeGuardPolicyStore = Depends(get_store),
):
    return _get("get_egress", policy_id, revision, principal, store)


@router.post("/data-classifications", response_model=DataClassificationPolicyRevision, status_code=status.HTTP_201_CREATED)
def publish_data_classification(
    body: DataClassificationPolicyRevisionCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str = Header(alias="If-Match"),
    principal: Principal = Depends(require_principal),
    store: AipRuntimeGuardPolicyStore = Depends(get_store),
):
    return _publish("publish_data_classification", body, idempotency_key, if_match, principal, store)


@router.get("/data-classifications/{policy_id}", response_model=DataClassificationPolicyRevision)
def get_data_classification(
    policy_id: str,
    revision: int | None = Query(default=None, ge=1),
    principal: Principal = Depends(require_principal),
    store: AipRuntimeGuardPolicyStore = Depends(get_store),
):
    return _get("get_data_classification", policy_id, revision, principal, store)
