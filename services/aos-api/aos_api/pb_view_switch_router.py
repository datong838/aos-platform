"W4 · 三种视图切换（220w L1176） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.pb_view_switch import (
    ViewSwitch,
    ViewSwitchEngine,
    ViewSwitchError,
    get_engine,
)

router = APIRouter(prefix="/api/pb/view-switch", tags=["PB View Switch"])


def _eng() -> ViewSwitchEngine:
    return get_engine()


@router.post("")
def create(item: ViewSwitch):
    try:
        return _eng().register(item)
    except ViewSwitchError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except ViewSwitchError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except ViewSwitchError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except ViewSwitchError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
