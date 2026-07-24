"W4 · 四种添加数据方式（220w L1183） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.pb_add_data_modes import (
    AddDataMode,
    AddDataModeEngine,
    AddDataModeError,
    get_engine,
)

router = APIRouter(prefix="/api/pb/add-data-modes", tags=["PB Add Data Modes"])


def _eng() -> AddDataModeEngine:
    return get_engine()


@router.post("")
def create(item: AddDataMode):
    try:
        return _eng().register(item)
    except AddDataModeError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except AddDataModeError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except AddDataModeError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except AddDataModeError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
