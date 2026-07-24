"W4 · transforms-external-systems（220w L835） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.di_transforms_external import (
    TransformsExternal,
    TransformsExternalEngine,
    TransformsExternalError,
    get_engine,
)

router = APIRouter(prefix="/api/di/transforms-external", tags=["DI Transforms External"])


def _eng() -> TransformsExternalEngine:
    return get_engine()


@router.post("")
def create(item: TransformsExternal):
    try:
        return _eng().register(item)
    except TransformsExternalError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except TransformsExternalError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except TransformsExternalError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except TransformsExternalError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
