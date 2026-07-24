"W4 · 属性和直方图面板（220w L530） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.dl_property_histogram import (
    PropertyHistogram,
    PropertyHistogramEngine,
    PropertyHistogramError,
    get_engine,
)

router = APIRouter(prefix="/api/dl/property-histogram", tags=["DL Property Histogram"])


def _eng() -> PropertyHistogramEngine:
    return get_engine()


@router.post("")
def create(item: PropertyHistogram):
    try:
        return _eng().register(item)
    except PropertyHistogramError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except PropertyHistogramError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except PropertyHistogramError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except PropertyHistogramError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
