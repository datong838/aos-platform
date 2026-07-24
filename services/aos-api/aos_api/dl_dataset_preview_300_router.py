"W4 · 数据集预览 300 行（220w L568） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.dl_dataset_preview_300 import (
    DatasetPreview300,
    DatasetPreview300Engine,
    DatasetPreview300Error,
    get_engine,
)

router = APIRouter(prefix="/api/dl/dataset-preview-300", tags=["DL Dataset Preview 300"])


def _eng() -> DatasetPreview300Engine:
    return get_engine()


@router.post("")
def create(item: DatasetPreview300):
    try:
        return _eng().register(item)
    except DatasetPreview300Error as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except DatasetPreview300Error as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except DatasetPreview300Error as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except DatasetPreview300Error as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
