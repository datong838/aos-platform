"W4 · Key by 主键/排序列（220w L695） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.di_key_by import (
    KeyBy,
    KeyByEngine,
    KeyByError,
    get_engine,
)

router = APIRouter(prefix="/api/di/key-by", tags=["DI Key By"])


def _eng() -> KeyByEngine:
    return get_engine()


@router.post("")
def create(item: KeyBy):
    try:
        return _eng().register(item)
    except KeyByError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except KeyByError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except KeyByError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except KeyByError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
