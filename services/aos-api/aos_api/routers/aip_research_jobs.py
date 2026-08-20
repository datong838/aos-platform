"""Tenant-scoped ResearchJob provider, event and delivery authority API."""

# FastAPI dependency injection intentionally evaluates Depends at import time.
# ruff: noqa: B008
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request

from aos_api.aip_research_job import (
    CancelResearchJobRequest,
    CreateResearchJobRequest,
    ReconcileResearchJobRequest,
    RecordResearchArtifactRequest,
    RecordResearchDeliveryRequest,
    RecordResearchSubmissionRequest,
    RegisterResearchProviderRequest,
    ResearchArtifactReceipt,
    ResearchDeliveryReceipt,
    ResearchJobEvent,
    ResearchJobListResponse,
    ResearchJobSnapshot,
    ResearchProviderRevision,
    ResearchSubmissionReceipt,
    RetryResearchJobRequest,
)
from aos_api.aip_research_job_service import AipResearchJobService
from aos_api.aip_research_job_store import (
    AipResearchJobBlocked,
    AipResearchJobConflict,
    AipResearchJobNotFound,
    AipResearchJobPersistenceError,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/research-authority", tags=["aip-research-authority"])
_SERVICE = AipResearchJobService()


def get_aip_research_job_service() -> AipResearchJobService:
    return _SERVICE


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _require_role(principal: Principal, allowed: set[str]) -> None:
    if not {role.lower() for role in principal.roles}.intersection(allowed):
        raise ApiError(
            code="AIP_SCOPE_FORBIDDEN",
            message="trusted ResearchJob role required",
            status_code=403,
        )


def _map_error(exc: Exception) -> ApiError:
    if isinstance(exc, AipResearchJobNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, AipResearchJobConflict):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, AipResearchJobBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    if isinstance(exc, AipResearchJobPersistenceError):
        return ApiError(
            code=exc.code,
            message="research job authority persistence is unavailable",
            status_code=503,
        )
    return ApiError(
        code="AIP_RESEARCH_JOB_FAILED",
        message="research job authority operation failed",
        status_code=500,
    )


@router.post("/providers/revisions", response_model=ResearchProviderRevision)
def register_provider(
    body: RegisterResearchProviderRequest,
    principal: Principal = Depends(require_principal),
    service: AipResearchJobService = Depends(get_aip_research_job_service),
) -> ResearchProviderRevision:
    _require_role(principal, {"admin"})
    try:
        return service.register_provider(_scope(principal), body, principal.subject)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/jobs", response_model=ResearchJobSnapshot)
def create_job(
    body: CreateResearchJobRequest,
    principal: Principal = Depends(require_principal),
    service: AipResearchJobService = Depends(get_aip_research_job_service),
) -> ResearchJobSnapshot:
    _require_role(principal, {"admin", "executor", "aip_executor"})
    try:
        return service.create_job(_scope(principal), body, principal.subject)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/jobs", response_model=ResearchJobListResponse)
def list_jobs(
    limit: int = 50,
    principal: Principal = Depends(require_principal),
    service: AipResearchJobService = Depends(get_aip_research_job_service),
) -> ResearchJobListResponse:
    try:
        return service.list_jobs(_scope(principal), limit=limit)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/jobs/{job_id}", response_model=ResearchJobSnapshot)
def get_job(
    job_id: str,
    principal: Principal = Depends(require_principal),
    service: AipResearchJobService = Depends(get_aip_research_job_service),
) -> ResearchJobSnapshot:
    try:
        return service.get_job(_scope(principal), job_id)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/jobs/{job_id}/cancel", response_model=ResearchJobSnapshot)
def cancel_job(
    job_id: str,
    body: CancelResearchJobRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1),
    principal: Principal = Depends(require_principal),
    service: AipResearchJobService = Depends(get_aip_research_job_service),
) -> ResearchJobSnapshot:
    _require_role(principal, {"admin", "executor", "aip_executor"})
    try:
        return service.cancel_job(
            _scope(principal),
            job_id,
            body,
            principal.subject,
            idempotency_key,
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/jobs/{job_id}/retry", response_model=ResearchJobSnapshot)
def retry_job(
    job_id: str,
    body: RetryResearchJobRequest,
    principal: Principal = Depends(require_principal),
    service: AipResearchJobService = Depends(get_aip_research_job_service),
) -> ResearchJobSnapshot:
    _require_role(principal, {"admin", "executor", "aip_executor"})
    try:
        return service.retry_job(
            _scope(principal), job_id, body, principal.subject
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/jobs/{job_id}/submission-receipts", response_model=ResearchSubmissionReceipt
)
def record_submission(
    job_id: str,
    body: RecordResearchSubmissionRequest,
    principal: Principal = Depends(require_principal),
    service: AipResearchJobService = Depends(get_aip_research_job_service),
) -> ResearchSubmissionReceipt:
    _require_role(principal, {"admin", "executor", "aip_executor"})
    if body.job_id != job_id:
        raise ApiError(
            code="AIP_INVALID_ARGUMENT",
            message="job path and body must match",
            status_code=400,
        )
    try:
        return service.record_submission(_scope(principal), body)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/jobs/{job_id}/events", response_model=ResearchJobSnapshot)
def record_event(
    job_id: str,
    body: ResearchJobEvent,
    principal: Principal = Depends(require_principal),
    service: AipResearchJobService = Depends(get_aip_research_job_service),
) -> ResearchJobSnapshot:
    _require_role(principal, {"admin", "executor", "aip_executor"})
    try:
        return service.record_event(_scope(principal), job_id, body)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/providers/{provider_id}/revisions/{provider_revision}/callbacks")
async def verify_callback(
    provider_id: str,
    provider_revision: int,
    request: Request,
    callback_timestamp: int = Header(alias="X-AIP-Callback-Timestamp"),
    callback_nonce: str = Header(alias="X-AIP-Callback-Nonce"),
    callback_signature: str = Header(alias="X-AIP-Callback-Signature"),
    principal: Principal = Depends(require_principal),
    service: AipResearchJobService = Depends(get_aip_research_job_service),
) -> dict[str, str]:
    _require_role(principal, {"admin", "executor", "aip_executor"})
    try:
        body_hash = service.verify_callback(
            _scope(principal),
            provider_id=provider_id,
            provider_revision=provider_revision,
            timestamp=callback_timestamp,
            nonce=callback_nonce,
            body=await request.body(),
            signature=callback_signature,
        )
        return {"bodyHash": body_hash, "action": "pull_provider_state"}
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/jobs/{job_id}/artifact-receipts", response_model=ResearchArtifactReceipt)
def record_artifact(
    job_id: str,
    body: RecordResearchArtifactRequest,
    principal: Principal = Depends(require_principal),
    service: AipResearchJobService = Depends(get_aip_research_job_service),
) -> ResearchArtifactReceipt:
    _require_role(principal, {"admin", "executor", "aip_executor"})
    if body.job_id != job_id:
        raise ApiError(
            code="AIP_INVALID_ARGUMENT",
            message="job path and body must match",
            status_code=400,
        )
    try:
        return service.record_artifact(_scope(principal), body, principal.subject)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/jobs/{job_id}/delivery-receipts", response_model=ResearchDeliveryReceipt)
def record_delivery(
    job_id: str,
    body: RecordResearchDeliveryRequest,
    principal: Principal = Depends(require_principal),
    service: AipResearchJobService = Depends(get_aip_research_job_service),
) -> ResearchDeliveryReceipt:
    _require_role(principal, {"admin", "executor", "aip_executor"})
    if body.job_id != job_id:
        raise ApiError(
            code="AIP_INVALID_ARGUMENT",
            message="job path and body must match",
            status_code=400,
        )
    try:
        return service.record_delivery(_scope(principal), body)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/jobs/{job_id}/reconcile-receipts", response_model=ResearchDeliveryReceipt
)
def reconcile(
    job_id: str,
    body: ReconcileResearchJobRequest,
    principal: Principal = Depends(require_principal),
    service: AipResearchJobService = Depends(get_aip_research_job_service),
) -> ResearchDeliveryReceipt:
    _require_role(principal, {"admin", "executor", "aip_executor"})
    if body.job_id != job_id:
        raise ApiError(
            code="AIP_INVALID_ARGUMENT",
            message="job path and body must match",
            status_code=400,
        )
    try:
        return service.reconcile(_scope(principal), body)
    except Exception as exc:
        raise _map_error(exc) from exc


__all__ = ["get_aip_research_job_service", "router"]
