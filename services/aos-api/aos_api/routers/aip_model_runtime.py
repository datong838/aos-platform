"""AIP-7 canonical exact model runtime API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, status

from aos_api.aip_model_runtime_contracts import (
    ModelRouteResolution, ModelRouteRevision, ProviderHealthObservation,
    ProviderInstanceRevision, RegisteredModelRevision, RuntimePolicyRevision,
)
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_model_runtime_store import (
    AipModelRuntimeStore, ModelRuntimeConflict, ModelRuntimeDependencyBlocked,
    ModelRuntimeIdempotencyConflict, ModelRuntimeNotFound, ModelRuntimeStoreError,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/model-runtime", tags=["aip-model-runtime"])
_STORE = AipModelRuntimeStore()


def get_store() -> AipModelRuntimeStore:
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


def _map(exc: ModelRuntimeStoreError) -> ApiError:
    if isinstance(exc, ModelRuntimeNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, (ModelRuntimeConflict, ModelRuntimeIdempotencyConflict)):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, ModelRuntimeDependencyBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    return ApiError(code=exc.code, message="model runtime persistence failed", status_code=503)


def _publish(kind: str, item, key: str, if_match: str, principal: Principal, store: AipModelRuntimeStore):
    normalized = item.model_copy(update={"created_by": principal.subject})
    try:
        return getattr(store, f"publish_{kind}")(_scope(principal), principal.subject, _key(key), normalized, expected_version=_version(if_match))
    except ModelRuntimeStoreError as exc:
        raise _map(exc) from exc


@router.post("/providers", response_model=ProviderInstanceRevision, status_code=status.HTTP_201_CREATED)
def publish_provider(body: ProviderInstanceRevision, idempotency_key: str = Header(alias="Idempotency-Key"), if_match: str = Header(alias="If-Match"), principal: Principal = Depends(require_principal), store: AipModelRuntimeStore = Depends(get_store)):
    return _publish("provider", body, idempotency_key, if_match, principal, store)


@router.post("/models", response_model=RegisteredModelRevision, status_code=status.HTTP_201_CREATED)
def publish_model(body: RegisteredModelRevision, idempotency_key: str = Header(alias="Idempotency-Key"), if_match: str = Header(alias="If-Match"), principal: Principal = Depends(require_principal), store: AipModelRuntimeStore = Depends(get_store)):
    return _publish("model", body, idempotency_key, if_match, principal, store)


@router.post("/policies", response_model=RuntimePolicyRevision, status_code=status.HTTP_201_CREATED)
def publish_policy(body: RuntimePolicyRevision, idempotency_key: str = Header(alias="Idempotency-Key"), if_match: str = Header(alias="If-Match"), principal: Principal = Depends(require_principal), store: AipModelRuntimeStore = Depends(get_store)):
    return _publish("policy", body, idempotency_key, if_match, principal, store)


@router.post("/routes", response_model=ModelRouteRevision, status_code=status.HTTP_201_CREATED)
def publish_route(body: ModelRouteRevision, idempotency_key: str = Header(alias="Idempotency-Key"), if_match: str = Header(alias="If-Match"), principal: Principal = Depends(require_principal), store: AipModelRuntimeStore = Depends(get_store)):
    return _publish("route", body, idempotency_key, if_match, principal, store)


@router.post("/provider-health", response_model=ProviderHealthObservation, status_code=status.HTTP_201_CREATED)
def record_health(body: ProviderHealthObservation, idempotency_key: str = Header(alias="Idempotency-Key"), principal: Principal = Depends(require_principal), store: AipModelRuntimeStore = Depends(get_store)):
    try:
        return store.record_health(_scope(principal), principal.subject, _key(idempotency_key), body)
    except ModelRuntimeStoreError as exc:
        raise _map(exc) from exc


@router.get("/routes/{route_id}", response_model=ModelRouteRevision)
def get_route(route_id: str, revision: int | None = Query(default=None, ge=1), principal: Principal = Depends(require_principal), store: AipModelRuntimeStore = Depends(get_store)):
    try:
        return store.get_route(_scope(principal), route_id, revision)
    except ModelRuntimeStoreError as exc:
        raise _map(exc) from exc


@router.get("/routes/{route_id}/resolution", response_model=ModelRouteResolution)
def resolve_route(route_id: str, principal: Principal = Depends(require_principal), store: AipModelRuntimeStore = Depends(get_store)):
    try:
        return AipModelRuntimeResolver(store).resolve(_scope(principal), route_id)
    except ModelRuntimeStoreError as exc:
        raise _map(exc) from exc
