"""W1-15 · Dataset Preview SQL Console API 路由。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from aos_api.sql_console import get_console

router = APIRouter(tags=["sql-console"])


class ExecuteRequest(BaseModel):
    rows: list[dict[str, Any]] = []
    table_name: str = "dataset"
    sql: str


class ValidateRequest(BaseModel):
    sql: str


class AutocompleteRequest(BaseModel):
    columns: list[str] = []
    prefix: str = ""


@router.post("/v1/sql-console/execute")
def execute_query(req: ExecuteRequest):
    result = get_console().execute(req.rows, req.table_name, req.sql)
    return result.model_dump()


@router.post("/v1/sql-console/validate")
def validate_query(req: ValidateRequest):
    errors = get_console().validate(req.sql)
    return {"errors": errors, "ok": len(errors) == 0}


@router.post("/v1/sql-console/autocomplete")
def autocomplete(req: AutocompleteRequest):
    suggestions = get_console().autocomplete(req.columns, req.prefix)
    return {"suggestions": [s.model_dump() for s in suggestions]}


@router.get("/v1/sql-console/history")
def list_history(limit: int = 50):
    records = get_console().list_history(limit)
    return {"history": [r.model_dump() for r in records], "count": len(records)}
