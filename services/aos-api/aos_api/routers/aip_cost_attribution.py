"""Tenant-scoped cost attribution and capability receipt authority API."""

# FastAPI dependency injection intentionally evaluates Depends at import time.
# ruff: noqa: B008
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from aos_api.aip_cost_attribution_service import AipCostAttributionService
from aos_api.aip_eval_authority_store import (
    AipEvalAuthorityConflict,
    AipEvalAuthorityNotFound,
    AipEvalAuthorityPersistenceError,
)
from aos_api.aip_eval_contracts import (
    AttributionSubjectType,
    CapabilityReceipt,
    CapabilityReceiptIngestRequest,
    CostAttributionSummary,
    UsageAttribution,
    UsageAttributionRequest,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/cost-authority", tags=["aip-cost-authority"])
_SERVICE = AipCostAttributionService()


def get_aip_cost_attribution_service() -> AipCostAttributionService:
    return _SERVICE


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _require_runtime(principal: Principal) -> None:
    if not {role.lower() for role in principal.roles}.intersection(
        {"admin", "executor", "aip_executor"}
    ):
        raise ApiError(
            code="AIP_SCOPE_FORBIDDEN",
            message="trusted runtime role required for cost authority ingestion",
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
            message="cost authority persistence is unavailable",
            status_code=503,
        )
    return ApiError(
        code="AIP_COST_AUTHORITY_FAILED",
        message="cost authority operation failed",
        status_code=500,
    )


@router.post("/capability-receipts", response_model=CapabilityReceipt)
def ingest_capability_receipt(
    body: CapabilityReceiptIngestRequest,
    principal: Principal = Depends(require_principal),
    service: AipCostAttributionService = Depends(get_aip_cost_attribution_service),
) -> CapabilityReceipt:
    _require_runtime(principal)
    try:
        return service.ingest_capability_receipt(_scope(principal), body)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/lineages/{lineage_id}/capability-receipts",
    response_model=list[CapabilityReceipt],
)
def list_capability_receipts(
    lineage_id: str,
    principal: Principal = Depends(require_principal),
    service: AipCostAttributionService = Depends(get_aip_cost_attribution_service),
) -> list[CapabilityReceipt]:
    try:
        return service.list_capability_receipts(_scope(principal), lineage_id)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/usage-attributions", response_model=UsageAttribution)
def attribute_usage(
    body: UsageAttributionRequest,
    principal: Principal = Depends(require_principal),
    service: AipCostAttributionService = Depends(get_aip_cost_attribution_service),
) -> UsageAttribution:
    _require_runtime(principal)
    try:
        return service.attribute_usage(_scope(principal), body)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/subjects/{subject_type}/{subject_id}/cost-summary",
    response_model=list[CostAttributionSummary],
)
def summarize_cost(
    subject_type: AttributionSubjectType,
    subject_id: str,
    subject_revision: str = Query(alias="subjectRevision", min_length=1),
    principal: Principal = Depends(require_principal),
    service: AipCostAttributionService = Depends(get_aip_cost_attribution_service),
) -> list[CostAttributionSummary]:
    try:
        return service.summarize_cost(
            _scope(principal),
            subject_type=subject_type,
            subject_id=subject_id,
            subject_revision=subject_revision,
        )
    except Exception as exc:
        raise _map_error(exc) from exc


__all__ = ["get_aip_cost_attribution_service", "router"]
