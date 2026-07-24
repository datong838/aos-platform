"""W2-#16 / W2-#17 · WriteMode + Transaction 状态机 API 路由。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.data_transaction import (
    TransactionError,
    TransactionStatus,
    describe_write_modes,
    get_store,
)
from aos_api.errors import ApiError

router = APIRouter(tags=["data-transactions"])


def _map_error(err: TransactionError, status: int = 400) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=status)


# ── WriteMode（W2-#16）──


@router.get("/v1/data-transactions/write-modes")
def list_write_modes():
    """返回所有写入模式说明。"""
    return {"modes": describe_write_modes()}


# ── Transaction 状态机（W2-#17）──


class BeginRequest(BaseModel):
    dataset_rid: str
    write_mode: str = "default"
    primary_key: str = "id"
    expectation_ids: list[str] = Field(default_factory=list)


class WriteRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/v1/data-transactions/begin")
def begin_transaction(req: BeginRequest):
    try:
        txn = get_store().begin(
            dataset_rid=req.dataset_rid,
            write_mode=req.write_mode,
            primary_key=req.primary_key,
            expectation_ids=req.expectation_ids,
        )
    except TransactionError as err:
        raise _map_error(err) from err
    return txn.model_dump()


@router.post("/v1/data-transactions/{txn_id}/write")
def write_transaction(txn_id: str, req: WriteRequest):
    try:
        txn = get_store().write(txn_id, req.rows)
    except TransactionError as err:
        status = 404 if err.code == "NOT_FOUND" else 400
        raise _map_error(err, status) from err
    return txn.model_dump()


@router.post("/v1/data-transactions/{txn_id}/commit")
def commit_transaction(txn_id: str):
    try:
        txn = get_store().commit(txn_id)
    except TransactionError as err:
        status = 404 if err.code == "NOT_FOUND" else 400
        raise _map_error(err, status) from err
    return txn.model_dump()


@router.post("/v1/data-transactions/{txn_id}/abort")
def abort_transaction(txn_id: str):
    try:
        txn = get_store().abort(txn_id)
    except TransactionError as err:
        status = 404 if err.code == "NOT_FOUND" else 400
        raise _map_error(err, status) from err
    return txn.model_dump()


@router.get("/v1/data-transactions/{txn_id}")
def get_transaction(txn_id: str):
    txn = get_store().get(txn_id)
    if txn is None:
        raise ApiError(code="NOT_FOUND", message=f"事务 {txn_id!r} 不存在", status_code=404)
    return txn.model_dump()


@router.get("/v1/data-transactions")
def list_transactions(dataset_rid: str | None = None):
    return {"transactions": [t.model_dump() for t in get_store().list(dataset_rid)]}
