"""W2-AW · Data Connection Extras 路由（#128 #129 #5）."""
from __future__ import annotations

from typing import Optional

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.auth import require_principal
from aos_api.data_connection_extras import (
    AgentMetrics,
    AgentMetricsError,
    CloudIdentity,
    CloudIdentityError,
    VirtualTable,
    VirtualTableError,
    get_agent_metrics_engine,
    get_cloud_identity_engine,
    get_virtual_table_engine,
)
from aos_api.errors import ApiError

router = APIRouter(
    prefix="/data-connection-extras",
    tags=["Data Connection Extras"],
)


# ── error mappers ──

def _map_identity_err(e: CloudIdentityError) -> HTTPException:
    mapping = {
        "MISSING_NAME": (400, "缺少 name"),
        "MISSING_PROVIDER": (400, "缺少 provider"),
        "INVALID_PROVIDER": (400, "provider 无效"),
        "INVALID_STATUS": (400, "状态无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


def _map_vtable_err(e: VirtualTableError) -> HTTPException:
    mapping = {
        "MISSING_NAME": (400, "缺少 name"),
        "MISSING_SOURCE_CONNECTION": (400, "缺少 source_connection_id"),
        "INVALID_SYNC_MODE": (400, "sync_mode 无效"),
        "INVALID_STATUS": (400, "状态无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


def _map_metrics_err(e: AgentMetricsError) -> HTTPException:
    mapping = {
        "MISSING_AGENT": (400, "缺少 agent_id"),
        "INVALID_STATUS": (400, "状态无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


# ════════════════════ #128 Cloud Identity ════════════════════

class ValidateConfigBody(BaseModel):
    provider: str
    config: dict = {}


@router.post("/cloud-identities", response_model=CloudIdentity)
def register_cloud_identity(identity: CloudIdentity, _=require_principal):
    try:
        return get_cloud_identity_engine().register_identity(identity)
    except CloudIdentityError as e:
        raise _map_identity_err(e) from e


@router.get("/cloud-identities", response_model=list[CloudIdentity])
def list_cloud_identities(
    provider: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    _=require_principal,
):
    return get_cloud_identity_engine().list_identities(
        provider=provider, status=status
    )


@router.post("/cloud-identities/validate-config")
def validate_cloud_identity_config(body: ValidateConfigBody, _=require_principal):
    return get_cloud_identity_engine().validate_config(
        provider=body.provider, config=body.config
    )


@router.get("/cloud-identities/{identity_id}", response_model=CloudIdentity)
def get_cloud_identity(identity_id: str, _=require_principal):
    try:
        return get_cloud_identity_engine().get_identity(identity_id)
    except CloudIdentityError as e:
        raise _map_identity_err(e) from e


@router.put("/cloud-identities/{identity_id}", response_model=CloudIdentity)
def update_cloud_identity(
    identity_id: str, updates: dict, _=require_principal
):
    try:
        return get_cloud_identity_engine().update_identity(identity_id, updates)
    except CloudIdentityError as e:
        raise _map_identity_err(e) from e


@router.delete("/cloud-identities/{identity_id}")
def delete_cloud_identity(identity_id: str, _=require_principal):
    return {"deleted": get_cloud_identity_engine().delete_identity(identity_id)}


# ════════════════════ #129 Virtual Table ════════════════════

@router.post("/virtual-tables", response_model=VirtualTable)
def register_virtual_table(table: VirtualTable, _=require_principal):
    try:
        return get_virtual_table_engine().register_table(table)
    except VirtualTableError as e:
        raise _map_vtable_err(e) from e


@router.get("/virtual-tables", response_model=list[VirtualTable])
def list_virtual_tables(
    source_connection_id: Optional[str] = Query(None),
    sync_mode: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    _=require_principal,
):
    return get_virtual_table_engine().list_tables(
        source_connection_id=source_connection_id,
        sync_mode=sync_mode,
        status=status,
    )


@router.get("/virtual-tables/{table_id}", response_model=VirtualTable)
def get_virtual_table(table_id: str, _=require_principal):
    try:
        return get_virtual_table_engine().get_table(table_id)
    except VirtualTableError as e:
        raise _map_vtable_err(e) from e


@router.post("/virtual-tables/{table_id}/sync", response_model=VirtualTable)
def sync_virtual_table(table_id: str, _=require_principal):
    try:
        return get_virtual_table_engine().sync_table(table_id)
    except VirtualTableError as e:
        raise _map_vtable_err(e) from e


@router.put("/virtual-tables/{table_id}", response_model=VirtualTable)
def update_virtual_table(table_id: str, updates: dict, _=require_principal):
    try:
        return get_virtual_table_engine().update_table(table_id, updates)
    except VirtualTableError as e:
        raise _map_vtable_err(e) from e


@router.delete("/virtual-tables/{table_id}")
def delete_virtual_table(table_id: str, _=require_principal):
    return {"deleted": get_virtual_table_engine().delete_table(table_id)}


# ════════════════════ #5 Agent Metrics ════════════════════

@router.post("/agent-metrics", response_model=AgentMetrics)
def record_agent_metrics(metrics: AgentMetrics, _=require_principal):
    try:
        return get_agent_metrics_engine().record_metrics(metrics)
    except AgentMetricsError as e:
        raise _map_metrics_err(e) from e


@router.get("/agent-metrics", response_model=list[AgentMetrics])
def list_agent_metrics(
    agent_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    _=require_principal,
):
    return get_agent_metrics_engine().list_metrics(
        agent_id=agent_id, status=status
    )


@router.get("/agent-metrics/latest-by-agent", response_model=list[AgentMetrics])
def list_latest_agent_metrics(_=require_principal):
    return get_agent_metrics_engine().list_latest_by_agent()


@router.get("/agent-metrics/summary")
def get_agent_metrics_summary(agent_id: str, _=require_principal):
    return get_agent_metrics_engine().get_agent_summary(agent_id)


@router.get("/agent-metrics/{metrics_id}", response_model=AgentMetrics)
def get_agent_metrics(metrics_id: str, _=require_principal):
    try:
        return get_agent_metrics_engine().get_metrics(metrics_id)
    except AgentMetricsError as e:
        raise _map_metrics_err(e) from e


@router.delete("/agent-metrics/prune")
def prune_agent_metrics(days: int = Query(30, ge=1), _=require_principal):
    removed = get_agent_metrics_engine().prune_old(days=days)
    return {"removed": removed}
