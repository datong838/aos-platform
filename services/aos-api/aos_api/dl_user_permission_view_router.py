"W4 · 用户视角权限（220w L634） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.dl_user_permission_view import (
    UserPermissionView,
    UserPermissionViewEngine,
    UserPermissionViewError,
    get_engine,
)

router = APIRouter(prefix="/api/dl/user-permission-view", tags=["DL User Permission View"])


def _eng() -> UserPermissionViewEngine:
    return get_engine()


@router.post("")
def create(item: UserPermissionView):
    try:
        return _eng().register(item)
    except UserPermissionViewError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except UserPermissionViewError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except UserPermissionViewError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except UserPermissionViewError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
