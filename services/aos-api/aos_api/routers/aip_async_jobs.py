"""Read-only AsyncJobProjection API (ResearchJob + QueryJob)."""

# ruff: noqa: B008
from __future__ import annotations

from fastapi import APIRouter, Depends

from aos_api.aip_async_job_projection import (
    AsyncJobProjectionResponse,
    list_async_job_projection,
)
from aos_api.auth import Principal, require_principal
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/async-jobs", tags=["aip-async-jobs"])


@router.get("", response_model=AsyncJobProjectionResponse)
def list_async_jobs(
    limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> AsyncJobProjectionResponse:
    return list_async_job_projection(
        TenantScope(principal.org_id, principal.project_id), limit=limit
    )
