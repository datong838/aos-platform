"""184m — TTL archive ops HTTP."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from aos_api.auth import Principal, require_principal
from aos_api import ttl_job

router = APIRouter(tags=["ops-ttl"])


class TtlRunIn(BaseModel):
    dryRun: bool = False


@router.get("/v1/ops/ttl/status")
def ttl_status(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    _ = principal
    return ttl_job.status_snapshot()


@router.post("/v1/ops/ttl/run")
def ttl_run(
    body: TtlRunIn | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    dry = bool(body.dryRun) if body else False
    return ttl_job.run_archive(dry_run=dry)
