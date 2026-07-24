"W4 · 导出 Java 代码（220w L1289） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.pb_export_java import (
    ExportJava,
    ExportJavaEngine,
    ExportJavaError,
    get_engine,
)

router = APIRouter(prefix="/api/pb/export-java", tags=["PB Export Java"])


def _eng() -> ExportJavaEngine:
    return get_engine()


@router.post("")
def create(item: ExportJava):
    try:
        return _eng().register(item)
    except ExportJavaError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except ExportJavaError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except ExportJavaError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except ExportJavaError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
