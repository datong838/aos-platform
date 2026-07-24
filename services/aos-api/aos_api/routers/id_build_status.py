"""W3 Task 7.6 · 搭建状态监控（220w L3656） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.id_build_status import (
    BuildStatus,
    BuildStatusMonitorEngine,
    BuildStatusMonitorError,
    get_engine,
)

router = APIRouter(prefix="/api/id/build-status", tags=['ID Build Status'])


def _eng() -> BuildStatusMonitorEngine:
    return get_engine()


@router.post("")
def create(item: BuildStatus):
    try:
        return _eng().register(item)
    except BuildStatusMonitorError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except BuildStatusMonitorError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except BuildStatusMonitorError as e:
        raise HTTPException(status_code=404 if e.code == "NOT_FOUND" else 400,
                            detail={"code": e.code, "message": e.message})


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except BuildStatusMonitorError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
