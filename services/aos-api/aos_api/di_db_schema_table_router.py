"W4 · Database/Schema/Table（220w L811） Router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aos_api.di_db_schema_table import (
    DbSchemaTable,
    DbSchemaTableEngine,
    DbSchemaTableError,
    get_engine,
)

router = APIRouter(prefix="/api/di/db-schema-table", tags=["DI DB Schema Table"])


def _eng() -> DbSchemaTableEngine:
    return get_engine()


@router.post("")
def create(item: DbSchemaTable):
    try:
        return _eng().register(item)
    except DbSchemaTableError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})


@router.get("")
def list_all(**kwargs):
    return _eng().list(**kwargs)


@router.get("/{item_id}")
def get_one(item_id: str):
    try:
        return _eng().get(item_id)
    except DbSchemaTableError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


@router.patch("/{item_id}")
def update_one(item_id: str, patch: dict):
    try:
        return _eng().update(item_id, patch)
    except DbSchemaTableError as e:
        raise HTTPException(
            status_code=404 if e.code == "NOT_FOUND" else 400,
            detail={"code": e.code, "message": e.message},
        )


@router.delete("/{item_id}")
def delete_one(item_id: str):
    try:
        _eng().delete(item_id)
        return {"ok": True}
    except DbSchemaTableError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
