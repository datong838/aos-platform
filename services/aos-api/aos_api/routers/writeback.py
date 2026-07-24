"""W1-6 · Action 写回协议 API 路由。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.errors import ApiError
from aos_api.writeback import WritebackError, WritebackOp, get_store

router = APIRouter(tags=["writeback"])


class BeginRequest(BaseModel):
    dataset_rid: str


class ApplyRequest(BaseModel):
    ops: list[WritebackOp]


class ViewRequest(BaseModel):
    base_rows: list[dict[str, Any]] = Field(default_factory=list)
    pk_field: str = "id"


def _map_error(err: WritebackError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


@router.post("/v1/writeback/begin")
def begin(req: BeginRequest):
    try:
        txn_id = get_store().begin(req.dataset_rid)
    except WritebackError as err:
        raise _map_error(err) from err
    return {"txn_id": txn_id, "dataset_rid": req.dataset_rid}


@router.post("/v1/writeback/{txn_id}/apply")
def apply_ops(txn_id: str, req: ApplyRequest):
    try:
        layer = get_store().apply(txn_id, req.ops)
    except WritebackError as err:
        raise _map_error(err) from err
    return layer.model_dump()


@router.post("/v1/writeback/{txn_id}/commit")
def commit_txn(txn_id: str):
    try:
        layer = get_store().commit(txn_id)
    except WritebackError as err:
        raise _map_error(err) from err
    return layer.model_dump()


@router.post("/v1/writeback/{txn_id}/rollback")
def rollback_txn(txn_id: str):
    try:
        layer = get_store().rollback(txn_id)
    except WritebackError as err:
        raise _map_error(err) from err
    return layer.model_dump()


@router.get("/v1/writeback/datasets/{dataset_rid}")
def get_layer(dataset_rid: str):
    layer = get_store().get_layer(dataset_rid)
    if layer is None:
        raise _map_error(WritebackError("NOT_FOUND", f"dataset {dataset_rid!r} 无 L1 覆盖层"), 404)
    return layer.model_dump()


@router.post("/v1/writeback/datasets/{dataset_rid}/view")
def view_merged(dataset_rid: str, req: ViewRequest):
    try:
        rows = get_store().view(dataset_rid, req.base_rows, req.pk_field)
    except WritebackError as err:
        raise _map_error(err) from err
    return {"rows": rows, "count": len(rows)}


class BindRequest(BaseModel):
    module_id: str


@router.post("/v1/writeback/datasets/{dataset_rid}/bind-workshop")
def bind_workshop(dataset_rid: str, req: BindRequest):
    """W2-#19 · 绑定 Workshop 模块（写回层挂到 Workshop 待提交视图）。"""
    try:
        layer = get_store().bind_workshop(dataset_rid, req.module_id)
    except WritebackError as err:
        raise _map_error(err) from err
    return layer.model_dump()


@router.post("/v1/writeback/datasets/{dataset_rid}/unbind-workshop")
def unbind_workshop(dataset_rid: str):
    """W2-#19 · 解绑 Workshop 模块。"""
    try:
        layer = get_store().unbind_workshop(dataset_rid)
    except WritebackError as err:
        raise _map_error(err) from err
    return layer.model_dump()


@router.get("/v1/writeback/workshop/{module_id}/preview")
def workshop_preview(module_id: str):
    """W2-#19 · 按 Workshop 模块预览绑定的写回层（待提交覆盖层摘要）。"""
    layers = get_store().list_by_workshop(module_id)
    items = []
    for layer in layers:
        entries = layer.entries
        items.append({
            "dataset_rid": layer.dataset_rid,
            "status": layer.status,
            "workshop_module": layer.workshop_module,
            "workshop_bound_at": layer.workshop_bound_at,
            "entry_count": len(entries),
            "deleted_count": sum(1 for e in entries.values() if e.deleted),
        })
    return {"module_id": module_id, "items": items, "count": len(items)}
