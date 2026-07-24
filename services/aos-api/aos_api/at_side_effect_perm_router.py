"W4 · 副作用权限（220w L2997） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.at_side_effect_perm import (
    SideEffectPerm,
    SideEffectPermEngine,
    SideEffectPermError,
    get_engine,
)

router = APIRouter(prefix="/api/at/side-effect-perm", tags=["AT Side Effect Perm"])


def _eng() -> SideEffectPermEngine:
    return get_engine()


@router.post("")
def create(item: SideEffectPerm):
    try:
        return _eng().register(item)
    except SideEffectPermError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except SideEffectPermError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except SideEffectPermError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except SideEffectPermError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
