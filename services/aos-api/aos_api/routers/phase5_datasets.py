"""Phase 5 · Datasets 路由.

datasets + preview + builds + health + sync-config.

TI-5 C2-B：``GET /v1/datasets`` 与 ``GET /v1/datasets/{id}`` 因 Router
注册顺序被 wave_ext Data OS 抢先匹配，本模块同名 GET 为
``NOT_REACHABLE_DUPLICATE``（manifest 仍登记 2 条，本波不改 route 契约）。
POST / preview / builds / health / sync-config 仍由本模块服务，存储已 scoped。
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from aos_api.auth import Principal, require_principal
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/datasets", tags=["phase5-datasets"])


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


# ─────────── Request models ───────────


class CreateDatasetRequest(BaseModel):
    name: str
    description: str = ""
    source_type: str = "database"
    source_uri: str = ""
    status: str = "active"
    schema: list[dict[str, Any]] = []
    row_count: int = 0
    size_bytes: int = 0


class UpdateSyncConfigRequest(BaseModel):
    mode: str | None = None
    interval_minutes: int | None = None
    enabled: bool | None = None


# ─────────── Dataset list + create ───────────


@router.get("")
async def list_datasets(
    principal: Annotated[Principal, Depends(require_principal)],
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    eng = get_engine()
    items, total = eng.list_datasets(
        _scope(principal), search=search, page=page, page_size=page_size
    )
    return {
        "items": [d.model_dump() for d in items],
        "total": total, "page": page, "page_size": page_size,
    }


@router.post("")
async def create_dataset(
    req: CreateDatasetRequest,
    principal: Annotated[Principal, Depends(require_principal)],
) -> dict[str, Any]:
    eng = get_engine()
    ds = eng.create_dataset(_scope(principal), **req.model_dump())
    return ds.model_dump()


# ─────────── Dataset detail (metadata + statistics + schema) ───────────


@router.get("/{ds_id}")
async def get_dataset(
    ds_id: str,
    principal: Annotated[Principal, Depends(require_principal)],
) -> dict[str, Any]:
    eng = get_engine()
    ds = eng.get_dataset(_scope(principal), ds_id)
    if ds is None:
        raise HTTPException(404, f"Dataset {ds_id} not found")
    result = ds.model_dump()
    # Add statistics
    result["statistics"] = {
        "row_count": ds.row_count,
        "size_bytes": ds.size_bytes,
        "size_mb": round(ds.size_bytes / (1024 * 1024), 2) if ds.size_bytes else 0,
        "column_count": len(ds.schema),
    }
    return result


# ─────────── Preview ───────────


@router.get("/{ds_id}/preview")
async def preview_dataset(
    ds_id: str,
    principal: Annotated[Principal, Depends(require_principal)],
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    eng = get_engine()
    try:
        return eng.preview_dataset(_scope(principal), ds_id, limit=limit)
    except KeyError:
        raise HTTPException(404, f"Dataset {ds_id} not found")


# ─────────── Builds ───────────


@router.get("/{ds_id}/builds")
async def list_builds(
    ds_id: str,
    principal: Annotated[Principal, Depends(require_principal)],
) -> dict[str, Any]:
    eng = get_engine()
    scope = _scope(principal)
    if eng.get_dataset(scope, ds_id) is None:
        raise HTTPException(404, f"Dataset {ds_id} not found")
    items = eng.list_builds(scope, ds_id)
    return {"items": [b.model_dump() for b in items], "count": len(items)}


# ─────────── Health ───────────


@router.get("/{ds_id}/health")
async def check_health(
    ds_id: str,
    principal: Annotated[Principal, Depends(require_principal)],
) -> dict[str, Any]:
    eng = get_engine()
    scope = _scope(principal)
    try:
        hc = eng.get_latest_health(scope, ds_id)
        if hc is None:
            hc = eng.check_health(scope, ds_id)
        return hc.model_dump()
    except KeyError:
        raise HTTPException(404, f"Dataset {ds_id} not found")


# ─────────── Sync config ───────────


@router.get("/{ds_id}/sync-config")
async def get_sync_config(
    ds_id: str,
    principal: Annotated[Principal, Depends(require_principal)],
) -> dict[str, Any]:
    eng = get_engine()
    try:
        return eng.get_sync_config(_scope(principal), ds_id).model_dump()
    except KeyError:
        raise HTTPException(404, f"Dataset {ds_id} not found")


@router.put("/{ds_id}/sync-config")
async def update_sync_config(
    ds_id: str,
    req: UpdateSyncConfigRequest,
    principal: Annotated[Principal, Depends(require_principal)],
) -> dict[str, Any]:
    eng = get_engine()
    try:
        data = {k: v for k, v in req.model_dump().items() if v is not None}
        sc = eng.set_sync_config(_scope(principal), ds_id, **data)
        return sc.model_dump()
    except KeyError:
        raise HTTPException(404, f"Dataset {ds_id} not found")
