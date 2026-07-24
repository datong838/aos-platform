"W4 · 输出路径配置（220w L812） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.di_output_path import (
    OutputPath,
    OutputPathEngine,
    OutputPathError,
    get_engine,
)

router = APIRouter(prefix="/api/di/output-path", tags=["DI Output Path"])


def _eng() -> OutputPathEngine:
    return get_engine()


@router.post("")
def create(item: OutputPath):
    try:
        return _eng().register(item)
    except OutputPathError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except OutputPathError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except OutputPathError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except OutputPathError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
