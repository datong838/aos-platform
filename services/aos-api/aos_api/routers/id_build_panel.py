"""W3 Task 7.5 · Build 面板（3种启动方式）（220w L3655） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.id_build_panel import (
    BuildPanelConfig,
    BuildPanelEngine,
    BuildPanelError,
    get_engine,
)

router = APIRouter(prefix="/api/id/build-panel", tags=['ID Build Panel'])


def _eng() -> BuildPanelEngine:
    return get_engine()


@router.post("")
def create(item: BuildPanelConfig):
    try:
        return _eng().register(item)
    except BuildPanelError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except BuildPanelError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except BuildPanelError as e:
        raise HTTPException(status_code=404 if e.code == "NOT_FOUND" else 400,
                            detail={"code": e.code, "message": e.message})


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except BuildPanelError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
