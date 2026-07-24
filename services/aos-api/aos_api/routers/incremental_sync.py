"""W2-23 · Data Connection 增量同步 API 路由。"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from aos_api.errors import ApiError
from aos_api.incremental_sync import (
    IncrementalConfig,
    IncrementalSyncEngine,
    IncrementalSyncError,
    SyncConnection,
    get_engine,
)

router = APIRouter(tags=["incremental-sync"])


def _map_error(err: IncrementalSyncError) -> ApiError:
    status = 404 if err.code == "NOT_FOUND" else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


class CreateConnectionRequest(BaseModel):
    name: str
    source_dataset_rid: str
    target_dataset_rid: str
    incremental_column: str = "updated_at"
    where_clause: str = ""
    batch_size: int = 1000


@router.post("/v1/incremental-sync/connections")
def create_connection(req: CreateConnectionRequest):
    conn = SyncConnection(
        name=req.name,
        source_dataset_rid=req.source_dataset_rid,
        target_dataset_rid=req.target_dataset_rid,
        config=IncrementalConfig(
            incremental_column=req.incremental_column,
            where_clause=req.where_clause,
            batch_size=req.batch_size,
        ),
    )
    return get_engine().create_connection(conn)


@router.get("/v1/incremental-sync/connections")
def list_connections():
    return {"items": get_engine().list_connections()}


@router.get("/v1/incremental-sync/connections/{conn_id}")
def get_connection(conn_id: str):
    conn = get_engine().get_connection(conn_id)
    if conn is None:
        raise ApiError(code="NOT_FOUND", message=f"同步连接 {conn_id} 不存在", status_code=404)
    return conn


@router.post("/v1/incremental-sync/connections/{conn_id}/sync")
def sync_connection(conn_id: str):
    try:
        return get_engine().sync(conn_id)
    except IncrementalSyncError as err:
        raise _map_error(err) from err


@router.post("/v1/incremental-sync/connections/{conn_id}/reset")
def reset_connection(conn_id: str):
    try:
        return get_engine().reset_state(conn_id)
    except IncrementalSyncError as err:
        raise _map_error(err) from err
