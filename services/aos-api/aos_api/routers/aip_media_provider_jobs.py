"""W7-07 tenant-scoped governed media Provider Job API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, status

from aos_api.aip_media_provider_job_contracts import (
    MediaProviderJob,
    MediaProviderJobEvent,
    MediaProviderJobListResponse,
    PrepareMediaProviderJobRequest,
    ProviderOperationResult,
)
from aos_api.aip_media_provider_job_service import AipMediaProviderJobService
from aos_api.aip_media_finance_store import AipMediaFinanceStore, MediaFinanceError
from aos_api.aip_media_provider_job_store import (
    AipMediaProviderJobStore,
    MediaProviderJobConflict,
    MediaProviderJobDependencyBlocked,
    MediaProviderJobError,
    MediaProviderJobNotFound,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope


router = APIRouter(prefix="/v1/aip/media-provider-jobs", tags=["aip-media-provider-jobs"])
_STORE = AipMediaProviderJobStore()
_FINANCE_STORE = AipMediaFinanceStore()
_SERVICE = AipMediaProviderJobService(store=_STORE, finance_submit_guard=_FINANCE_STORE)
_CONTROL_ROLES = frozenset({"admin", "executor", "aip_executor"})


def get_media_provider_job_store() -> AipMediaProviderJobStore:
    return _STORE


def get_media_provider_job_service() -> AipMediaProviderJobService:
    return _SERVICE


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _control_role(principal: Principal) -> None:
    if not _CONTROL_ROLES.intersection({item.lower() for item in principal.roles}):
        raise ApiError(
            code="MEDIA_PROVIDER_JOB_ROLE_REQUIRED",
            message="trusted media Provider Job executor role required",
            status_code=403,
        )


def _map(exc: MediaProviderJobError) -> ApiError:
    if isinstance(exc, MediaProviderJobNotFound):
        return ApiError(code=exc.code, message="media Provider Job not found", status_code=404)
    if isinstance(exc, MediaProviderJobConflict):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, MediaProviderJobDependencyBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    return ApiError(code=exc.code, message="media Provider Job authority unavailable", status_code=503)


def _control(
    operation: str,
    job_id: str,
    key: str,
    expected_sequence: int,
    principal: Principal,
    service: AipMediaProviderJobService,
) -> MediaProviderJob:
    _control_role(principal)
    try:
        return getattr(service, operation)(
            _scope(principal), principal.subject, job_id, key,
            expected_sequence=expected_sequence,
        )
    except MediaFinanceError as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=422) from exc
    except MediaProviderJobError as exc:
        raise _map(exc) from exc


@router.post("", response_model=MediaProviderJob, status_code=status.HTTP_201_CREATED)
def prepare_media_provider_job(
    body: PrepareMediaProviderJobRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120),
    principal: Principal = Depends(require_principal),
    service: AipMediaProviderJobService = Depends(get_media_provider_job_service),
) -> MediaProviderJob:
    _control_role(principal)
    try:
        return service.prepare(_scope(principal), principal.subject, idempotency_key, body)
    except MediaProviderJobError as exc:
        raise _map(exc) from exc


@router.get("", response_model=MediaProviderJobListResponse)
def list_media_provider_jobs(
    limit: int = Query(default=100, ge=1, le=100),
    principal: Principal = Depends(require_principal),
    store: AipMediaProviderJobStore = Depends(get_media_provider_job_store),
) -> MediaProviderJobListResponse:
    try:
        return store.list_jobs(_scope(principal), limit=limit)
    except MediaProviderJobError as exc:
        raise _map(exc) from exc


@router.get("/{job_id}", response_model=MediaProviderJob)
def get_media_provider_job(
    job_id: str,
    principal: Principal = Depends(require_principal),
    store: AipMediaProviderJobStore = Depends(get_media_provider_job_store),
) -> MediaProviderJob:
    try:
        return store.get_job(_scope(principal), job_id)
    except MediaProviderJobError as exc:
        raise _map(exc) from exc


@router.get("/{job_id}/events", response_model=list[MediaProviderJobEvent])
def list_media_provider_job_events(
    job_id: str,
    principal: Principal = Depends(require_principal),
    store: AipMediaProviderJobStore = Depends(get_media_provider_job_store),
) -> list[MediaProviderJobEvent]:
    try:
        return store.list_events(_scope(principal), job_id)
    except MediaProviderJobError as exc:
        raise _map(exc) from exc


@router.post("/{job_id}/submit", response_model=MediaProviderJob)
def submit_media_provider_job(job_id: str, expected_sequence: int = Header(alias="If-Match", ge=1), idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), service: AipMediaProviderJobService = Depends(get_media_provider_job_service)) -> MediaProviderJob:
    return _control("submit", job_id, idempotency_key, expected_sequence, principal, service)


@router.post("/{job_id}/status", response_model=MediaProviderJob)
def refresh_media_provider_job(job_id: str, expected_sequence: int = Header(alias="If-Match", ge=1), idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), service: AipMediaProviderJobService = Depends(get_media_provider_job_service)) -> MediaProviderJob:
    return _control("status", job_id, idempotency_key, expected_sequence, principal, service)


@router.post("/{job_id}/cancel", response_model=MediaProviderJob)
def cancel_media_provider_job(job_id: str, expected_sequence: int = Header(alias="If-Match", ge=1), idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), service: AipMediaProviderJobService = Depends(get_media_provider_job_service)) -> MediaProviderJob:
    return _control("cancel", job_id, idempotency_key, expected_sequence, principal, service)


@router.post("/{job_id}/reconcile", response_model=MediaProviderJob)
def reconcile_media_provider_job(job_id: str, expected_sequence: int = Header(alias="If-Match", ge=1), idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), service: AipMediaProviderJobService = Depends(get_media_provider_job_service)) -> MediaProviderJob:
    return _control("reconcile", job_id, idempotency_key, expected_sequence, principal, service)


@router.post("/{job_id}/webhook-observation", response_model=MediaProviderJob)
def observe_media_provider_webhook(job_id: str, body: ProviderOperationResult, expected_sequence: int = Header(alias="If-Match", ge=1), idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), service: AipMediaProviderJobService = Depends(get_media_provider_job_service)) -> MediaProviderJob:
    _control_role(principal)
    try:
        return service.observe_webhook(
            _scope(principal), principal.subject, job_id, idempotency_key, body,
            expected_sequence=expected_sequence,
        )
    except MediaProviderJobError as exc:
        raise _map(exc) from exc


__all__ = ["router"]
