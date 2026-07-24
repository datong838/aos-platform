"W4 · 图表平移模式（220w L1009） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.pp_chart_pan import (
    ChartPan,
    ChartPanEngine,
    ChartPanError,
    get_engine,
)

router = APIRouter(prefix="/api/pp/chart-pan", tags=["PP Chart Pan"])


def _eng() -> ChartPanEngine:
    return get_engine()


@router.post("")
def create(item: ChartPan):
    try:
        return _eng().register(item)
    except ChartPanError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except ChartPanError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except ChartPanError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except ChartPanError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
