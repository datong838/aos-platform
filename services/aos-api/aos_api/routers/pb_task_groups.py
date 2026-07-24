"""W3 Task 5.4 · 任务组（输出分配/计算配置文件/权限继承）（220w L1242） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.pb_task_groups import (
    TaskGroup,
    TaskGroupsEngine,
    TaskGroupsError,
    get_engine,
)

router = APIRouter(prefix="/api/pb/task-groups", tags=['PB Task Groups'])


def _eng() -> TaskGroupsEngine:
    return get_engine()


@router.post("")
def create(item: TaskGroup):
    try:
        return _eng().register(item)
    except TaskGroupsError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except TaskGroupsError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except TaskGroupsError as e:
        raise HTTPException(status_code=404 if e.code == "NOT_FOUND" else 400,
                            detail={"code": e.code, "message": e.message})


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except TaskGroupsError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
