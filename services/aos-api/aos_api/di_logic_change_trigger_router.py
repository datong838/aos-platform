"W4 · 逻辑变更触发（220w L892） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.di_logic_change_trigger import (
    LogicChangeTrigger,
    LogicChangeTriggerEngine,
    LogicChangeTriggerError,
    get_engine,
)

router = APIRouter(prefix="/api/di/logic-change-trigger", tags=["DI Logic Change"])


def _eng() -> LogicChangeTriggerEngine:
    return get_engine()


@router.post("")
def create(item: LogicChangeTrigger):
    try:
        return _eng().register(item)
    except LogicChangeTriggerError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except LogicChangeTriggerError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except LogicChangeTriggerError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except LogicChangeTriggerError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
