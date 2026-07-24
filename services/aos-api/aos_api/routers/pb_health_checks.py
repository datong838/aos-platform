"""W3 Task 5.5 · 健康检查配置（任务级/搭建级/新鲜度检查）（220w L1265） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.pb_health_checks import (
    HealthCheckConfig,
    HealthCheckEngine,
    HealthCheckError,
    get_engine,
)

router = APIRouter(prefix="/api/pb/health-checks", tags=['PB Health Checks'])


def _eng() -> HealthCheckEngine:
    return get_engine()


@router.post("")
def create(item: HealthCheckConfig):
    try:
        return _eng().register(item)
    except HealthCheckError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except HealthCheckError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except HealthCheckError as e:
        raise HTTPException(status_code=404 if e.code == "NOT_FOUND" else 400,
                            detail={"code": e.code, "message": e.message})


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except HealthCheckError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
