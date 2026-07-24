"W4 · 测试连接+建议（220w L245） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.dc_test_connection import (
    TestConnection,
    TestConnectionEngine,
    TestConnectionError,
    get_engine,
)

router = APIRouter(prefix="/api/dc/test-connection", tags=["DC Test Connection"])


def _eng() -> TestConnectionEngine:
    return get_engine()


@router.post("")
def create(item: TestConnection):
    try:
        return _eng().register(item)
    except TestConnectionError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except TestConnectionError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except TestConnectionError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except TestConnectionError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
