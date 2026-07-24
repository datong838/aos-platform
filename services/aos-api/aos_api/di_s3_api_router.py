"W4 · S3 API 协议暴露（220w L930） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.di_s3_api import (
    S3Api,
    S3ApiEngine,
    S3ApiError,
    get_engine,
)

router = APIRouter(prefix="/api/di/s3-api", tags=["DI S3 API"])


def _eng() -> S3ApiEngine:
    return get_engine()


@router.post("")
def create(item: S3Api):
    try:
        return _eng().register(item)
    except S3ApiError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except S3ApiError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except S3ApiError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except S3ApiError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
