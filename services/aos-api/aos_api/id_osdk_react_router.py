"W4 · OSDK React 应用开发（220w L3624） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.id_osdk_react import (
    OsdkReact,
    OsdkReactEngine,
    OsdkReactError,
    get_engine,
)

router = APIRouter(prefix="/api/id/osdk-react", tags=["ID OSDK React"])


def _eng() -> OsdkReactEngine:
    return get_engine()


@router.post("")
def create(item: OsdkReact):
    try:
        return _eng().register(item)
    except OsdkReactError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except OsdkReactError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except OsdkReactError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except OsdkReactError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
