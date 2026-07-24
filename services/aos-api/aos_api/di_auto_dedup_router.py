"W4 · 自动去重（220w L787） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.di_auto_dedup import (
    AutoDedup,
    AutoDedupEngine,
    AutoDedupError,
    get_engine,
)

router = APIRouter(prefix="/api/di/auto-dedup", tags=["DI Auto Dedup"])


def _eng() -> AutoDedupEngine:
    return get_engine()


@router.post("")
def create(item: AutoDedup):
    try:
        return _eng().register(item)
    except AutoDedupError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except AutoDedupError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except AutoDedupError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except AutoDedupError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
