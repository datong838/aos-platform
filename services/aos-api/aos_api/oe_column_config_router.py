"W4 · 列排序/配置/冻结/编辑（220w L2700） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.oe_column_config import (
    OeColumnConfig,
    OeColumnConfigEngine,
    OeColumnConfigError,
    get_engine,
)

router = APIRouter(prefix="/api/oe/column-config", tags=["OE Column Config"])


def _eng() -> OeColumnConfigEngine:
    return get_engine()


@router.post("")
def create(item: OeColumnConfig):
    try:
        return _eng().register(item)
    except OeColumnConfigError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except OeColumnConfigError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except OeColumnConfigError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except OeColumnConfigError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
