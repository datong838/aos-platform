"W4 · Funnel Pipeline 状态页（220w L2805） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.fn_pipeline_status import (
    FnPipelineStatus,
    FnPipelineStatusEngine,
    FnPipelineStatusError,
    get_engine,
)

router = APIRouter(prefix="/api/fn/pipeline-status", tags=["FN Pipeline Status"])


def _eng() -> FnPipelineStatusEngine:
    return get_engine()


@router.post("")
def create(item: FnPipelineStatus):
    try:
        return _eng().register(item)
    except FnPipelineStatusError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except FnPipelineStatusError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except FnPipelineStatusError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except FnPipelineStatusError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
