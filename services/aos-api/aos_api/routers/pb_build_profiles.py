"""W3 Task 5.3 · 搭建设置（9种批处理+6种流式计算配置文件）（220w L1236） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.pb_build_profiles import (
    BuildProfile,
    BuildProfilesEngine,
    BuildProfilesError,
    get_engine,
)

router = APIRouter(prefix="/api/pb/build-profiles", tags=['PB Build Profiles'])


def _eng() -> BuildProfilesEngine:
    return get_engine()


@router.post("")
def create(item: BuildProfile):
    try:
        return _eng().register(item)
    except BuildProfilesError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except BuildProfilesError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except BuildProfilesError as e:
        raise HTTPException(status_code=404 if e.code == "NOT_FOUND" else 400,
                            detail={"code": e.code, "message": e.message})


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except BuildProfilesError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
