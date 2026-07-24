"""W3 Task 7.4 · Python Transform 预览（220w L3623） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.id_py_transform_preview import (
    TransformPreview,
    PyTransformPreviewEngine,
    PyTransformPreviewError,
    get_engine,
)

router = APIRouter(prefix="/api/id/py-transform-preview", tags=['ID Py Transform Preview'])


def _eng() -> PyTransformPreviewEngine:
    return get_engine()


@router.post("")
def create(item: TransformPreview):
    try:
        return _eng().register(item)
    except PyTransformPreviewError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except PyTransformPreviewError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except PyTransformPreviewError as e:
        raise HTTPException(status_code=404 if e.code == "NOT_FOUND" else 400,
                            detail={"code": e.code, "message": e.message})


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except PyTransformPreviewError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
