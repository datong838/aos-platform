"W4 · Marketplace 打包（220w L1290） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.pb_marketplace_pkg import (
    MarketplacePkg,
    MarketplacePkgEngine,
    MarketplacePkgError,
    get_engine,
)

router = APIRouter(prefix="/api/pb/marketplace-pkg", tags=["PB Marketplace Pkg"])


def _eng() -> MarketplacePkgEngine:
    return get_engine()


@router.post("")
def create(item: MarketplacePkg):
    try:
        return _eng().register(item)
    except MarketplacePkgError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except MarketplacePkgError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except MarketplacePkgError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except MarketplacePkgError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
