"""W3 Task 3.4 · 过时数据集诊断（220w L652） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.dl_stale_diagnosis import (
    StaleDiagnosis,
    StaleDiagnosisEngine,
    StaleDiagnosisError,
    get_engine,
)

router = APIRouter(prefix="/api/dl/stale-diagnosis", tags=['DL Stale Diagnosis'])


def _eng() -> StaleDiagnosisEngine:
    return get_engine()


@router.post("")
def create(item: StaleDiagnosis):
    try:
        return _eng().register(item)
    except StaleDiagnosisError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except StaleDiagnosisError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except StaleDiagnosisError as e:
        raise HTTPException(status_code=404 if e.code == "NOT_FOUND" else 400,
                            detail={"code": e.code, "message": e.message})


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except StaleDiagnosisError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
