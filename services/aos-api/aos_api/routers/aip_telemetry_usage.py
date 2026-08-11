"""Tenant-scoped canonical telemetry and provider usage authority API."""

# FastAPI dependency injection intentionally evaluates Depends at import time.
# ruff: noqa: B008
from __future__ import annotations

from fastapi import APIRouter, Depends

from aos_api.aip_eval_authority_store import (
    AipEvalAuthorityConflict,
    AipEvalAuthorityNotFound,
    AipEvalAuthorityPersistenceError,
)
from aos_api.aip_eval_contracts import (
    TelemetrySpan,
    TelemetrySpanIngestRequest,
    UsageAdjustment,
    UsageAdjustmentRequest,
    UsageReceipt,
    UsageReceiptIngestRequest,
)
from aos_api.aip_telemetry_usage_service import AipTelemetryUsageService
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(
    prefix="/v1/aip/telemetry-authority", tags=["aip-telemetry-authority"]
)
_SERVICE = AipTelemetryUsageService()


def get_aip_telemetry_usage_service() -> AipTelemetryUsageService:
    return _SERVICE


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _require_runtime(principal: Principal) -> None:
    if not {role.lower() for role in principal.roles}.intersection(
        {"admin", "executor", "aip_executor"}
    ):
        raise ApiError(
            code="AIP_SCOPE_FORBIDDEN",
            message="trusted runtime role required for telemetry ingestion",
            status_code=403,
        )


def _map_error(exc: Exception) -> ApiError:
    if isinstance(exc, AipEvalAuthorityNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, AipEvalAuthorityConflict):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, AipEvalAuthorityPersistenceError):
        return ApiError(
            code=exc.code,
            message="telemetry authority persistence is unavailable",
            status_code=503,
        )
    return ApiError(
        code="AIP_TELEMETRY_AUTHORITY_FAILED",
        message="telemetry authority operation failed",
        status_code=500,
    )


@router.post("/spans", response_model=TelemetrySpan)
def ingest_span(
    body: TelemetrySpanIngestRequest,
    principal: Principal = Depends(require_principal),
    service: AipTelemetryUsageService = Depends(get_aip_telemetry_usage_service),
) -> TelemetrySpan:
    _require_runtime(principal)
    try:
        return service.ingest_span(_scope(principal), body)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/lineages/{lineage_id}/spans", response_model=list[TelemetrySpan])
def list_spans(
    lineage_id: str,
    principal: Principal = Depends(require_principal),
    service: AipTelemetryUsageService = Depends(get_aip_telemetry_usage_service),
) -> list[TelemetrySpan]:
    try:
        return service.list_spans(_scope(principal), lineage_id)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/usage-receipts", response_model=UsageReceipt)
def ingest_usage(
    body: UsageReceiptIngestRequest,
    principal: Principal = Depends(require_principal),
    service: AipTelemetryUsageService = Depends(get_aip_telemetry_usage_service),
) -> UsageReceipt:
    _require_runtime(principal)
    try:
        return service.ingest_usage(_scope(principal), body)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/lineages/{lineage_id}/usage-receipts", response_model=list[UsageReceipt])
def list_usage(
    lineage_id: str,
    principal: Principal = Depends(require_principal),
    service: AipTelemetryUsageService = Depends(get_aip_telemetry_usage_service),
) -> list[UsageReceipt]:
    try:
        return service.list_usage(_scope(principal), lineage_id)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/usage-adjustments", response_model=UsageAdjustment)
def append_adjustment(
    body: UsageAdjustmentRequest,
    principal: Principal = Depends(require_principal),
    service: AipTelemetryUsageService = Depends(get_aip_telemetry_usage_service),
) -> UsageAdjustment:
    _require_runtime(principal)
    try:
        return service.append_adjustment(
            _scope(principal), body, actor=principal.subject
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/usage-receipts/{receipt_id}/adjustments",
    response_model=list[UsageAdjustment],
)
def list_adjustments(
    receipt_id: str,
    principal: Principal = Depends(require_principal),
    service: AipTelemetryUsageService = Depends(get_aip_telemetry_usage_service),
) -> list[UsageAdjustment]:
    try:
        return service.list_adjustments(_scope(principal), receipt_id)
    except Exception as exc:
        raise _map_error(exc) from exc


__all__ = ["get_aip_telemetry_usage_service", "router"]
