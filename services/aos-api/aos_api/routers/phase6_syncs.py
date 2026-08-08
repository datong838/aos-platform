"""Phase 6 · Syncs 路由 (同步管理)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from aos_api.auth import Principal, require_principal
from aos_api.phase6_datasource_engine import get_engine
from aos_api.tenant_scope import TenantScope

router = APIRouter(
    prefix="/api/datasource/syncs",
    tags=["phase6-syncs"],
    dependencies=[Depends(require_principal)],
)


class CreateSyncRequest(BaseModel):
    name: str
    source_id: str
    target_dataset: str = ""
    mode: str = "full"
    cron_expr: str = "0 * * * *"
    status: str = "active"
    owner: str = "system"
    config: dict[str, Any] = {}


class UpdateSyncRequest(BaseModel):
    name: str | None = None
    source_id: str | None = None
    target_dataset: str | None = None
    mode: str | None = None
    cron_expr: str | None = None
    status: str | None = None
    owner: str | None = None
    config: dict[str, Any] | None = None


@router.get("")
async def list_syncs(
    principal: Principal = Depends(require_principal),
    search: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """D4 Phase C · C4: 列表按 principal 自动租户隔离。

    scope 来自 Principal（org_id+project_id），不传时降级到全局字典（向后兼容）。
    """
    eng = get_engine()
    scope = TenantScope(org_id=principal.org_id, project_id=principal.project_id)
    items, total = eng.list_sync_tasks(
        search=search, status=status, page=page, page_size=page_size, scope=scope,
    )
    return {"items": [s.model_dump() for s in items], "total": total, "page": page, "page_size": page_size}


@router.post("")
async def create_sync(
    req: CreateSyncRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """D4 Phase C · C4: 创建 SyncTask 时绑定 principal 的租户。"""
    eng = get_engine()
    scope = TenantScope(org_id=principal.org_id, project_id=principal.project_id)
    s = eng.create_sync_task(scope=scope, **req.model_dump())
    return s.model_dump()


@router.get("/{sync_id}")
async def get_sync(sync_id: str) -> dict[str, Any]:
    eng = get_engine()
    s = eng.get_sync_task(sync_id)
    if s is None:
        raise HTTPException(404, f"Sync {sync_id} not found")
    return s.model_dump()


@router.put("/{sync_id}")
async def update_sync(sync_id: str, req: UpdateSyncRequest) -> dict[str, Any]:
    eng = get_engine()
    try:
        data = {k: v for k, v in req.model_dump().items() if v is not None}
        s = eng.update_sync_task(sync_id, **data)
        return s.model_dump()
    except KeyError:
        raise HTTPException(404, f"Sync {sync_id} not found")


@router.post("/{sync_id}/run")
async def run_sync(sync_id: str) -> dict[str, Any]:
    eng = get_engine()
    try:
        run = eng.run_sync_task(sync_id)
        return run.model_dump()
    except KeyError:
        raise HTTPException(404, f"Sync {sync_id} not found")


@router.get("/{sync_id}/runs")
async def list_sync_runs(
    sync_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """D4 Phase C · C4: 查询 SyncTask 运行历史，按 principal 租户隔离。"""
    eng = get_engine()
    scope = TenantScope(org_id=principal.org_id, project_id=principal.project_id)
    if eng.get_sync_task(sync_id, scope=scope) is None:
        raise HTTPException(404, f"Sync {sync_id} not found")
    items = eng.list_sync_runs(sync_id, scope=scope)
    return {"items": [r.model_dump() for r in items], "count": len(items)}
