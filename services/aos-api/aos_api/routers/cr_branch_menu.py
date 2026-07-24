"""W3 Task 6.1 · 分支操作菜单（220w L1813） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.cr_branch_menu import (
    BranchAction,
    BranchMenuEngine,
    BranchMenuError,
    get_engine,
)

router = APIRouter(prefix="/api/cr/branch-menu", tags=['CR Branch Menu'])


def _eng() -> BranchMenuEngine:
    return get_engine()


@router.post("")
def create(item: BranchAction):
    try:
        return _eng().register(item)
    except BranchMenuError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except BranchMenuError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except BranchMenuError as e:
        raise HTTPException(status_code=404 if e.code == "NOT_FOUND" else 400,
                            detail={"code": e.code, "message": e.message})


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except BranchMenuError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
