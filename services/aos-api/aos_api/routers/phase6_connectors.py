"""Phase 6 · Connectors 路由."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from aos_api.auth import require_principal
from aos_api.phase6_datasource_engine import get_engine

router = APIRouter(
    prefix="/api/datasource/connectors",
    tags=["phase6-connectors"],
    dependencies=[Depends(require_principal)],
)


class CreateConnectorRequest(BaseModel):
    name: str
    connector_type: str = "database"
    version: str = "1.0.0"
    description: str = ""
    capabilities: list[str] = []
    config_schema: dict[str, Any] = {}
    status: str = "active"


class UpdateConnectorRequest(BaseModel):
    name: str | None = None
    connector_type: str | None = None
    version: str | None = None
    description: str | None = None
    capabilities: list[str] | None = None
    config_schema: dict[str, Any] | None = None
    status: str | None = None


@router.get("")
async def list_connectors(
    connector_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    eng = get_engine()
    items, total = eng.list_connectors(connector_type=connector_type, page=page, page_size=page_size)
    return {"items": [c.model_dump() for c in items], "total": total, "page": page, "page_size": page_size}


@router.post("")
async def create_connector(req: CreateConnectorRequest) -> dict[str, Any]:
    eng = get_engine()
    c = eng.create_connector(**req.model_dump())
    return c.model_dump()


@router.get("/{connector_id}")
async def get_connector(connector_id: str) -> dict[str, Any]:
    eng = get_engine()
    c = eng.get_connector(connector_id)
    if c is None:
        raise HTTPException(404, f"Connector {connector_id} not found")
    return c.model_dump()


@router.put("/{connector_id}")
async def update_connector(connector_id: str, req: UpdateConnectorRequest) -> dict[str, Any]:
    eng = get_engine()
    try:
        data = {k: v for k, v in req.model_dump().items() if v is not None}
        c = eng.update_connector(connector_id, **data)
        return c.model_dump()
    except KeyError:
        raise HTTPException(404, f"Connector {connector_id} not found")


@router.delete("/{connector_id}")
async def uninstall_connector(connector_id: str) -> dict[str, Any]:
    """卸载（删除）连接器。

    D4 Phase C: 新增卸载端点，支持删除不通用的专属插件（如 niushop-mysql）。
    """
    eng = get_engine()
    ok = eng.delete_connector(connector_id)
    if not ok:
        raise HTTPException(404, f"Connector {connector_id} not found")
    return {"connector_id": connector_id, "status": "uninstalled"}


@router.get("/{connector_id}/capabilities")
async def get_capabilities(connector_id: str) -> dict[str, Any]:
    eng = get_engine()
    try:
        caps = eng.get_connector_capabilities(connector_id)
        return {"connector_id": connector_id, "capabilities": caps}
    except KeyError:
        raise HTTPException(404, f"Connector {connector_id} not found")
