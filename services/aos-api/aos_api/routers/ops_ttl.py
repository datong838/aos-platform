"""184m — TTL archive ops HTTP."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from aos_api import ttl_job
from aos_api.auth import Principal, require_principal
from aos_api.tenant_scope import TenantScope

router = APIRouter(tags=["ops-ttl"])


class TtlRunIn(BaseModel):
    dryRun: bool = False


@router.get("/v1/ops/ttl/status")
def ttl_status(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    return ttl_job.status_snapshot(TenantScope(principal.org_id, principal.project_id))


@router.post("/v1/ops/ttl/run")
def ttl_run(
    body: TtlRunIn | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    dry = bool(body.dryRun) if body else False
    return ttl_job.run_archive(
        TenantScope(principal.org_id, principal.project_id), dry_run=dry
    )
