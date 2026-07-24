"W4 · FAQ 问题排查（220w L653） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.dl_faq_troubleshoot import (
    FaqTroubleshoot,
    FaqTroubleshootEngine,
    FaqTroubleshootError,
    get_engine,
)

router = APIRouter(prefix="/api/dl/faq-troubleshoot", tags=["DL FAQ Troubleshoot"])


def _eng() -> FaqTroubleshootEngine:
    return get_engine()


@router.post("")
def create(item: FaqTroubleshoot):
    try:
        return _eng().register(item)
    except FaqTroubleshootError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except FaqTroubleshootError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except FaqTroubleshootError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except FaqTroubleshootError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
