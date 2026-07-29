"""Phase 6 · Schemas 路由 (Schema 探索)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.phase6_datasource_engine import get_engine

router = APIRouter(prefix="/api/datasource", tags=["phase6-schemas"])


class PreviewRequest(BaseModel):
    schema_name: str = ""
    table_name: str = ""
    limit: int = 50


def _demo_schemas(source_id: str) -> list[dict[str, Any]]:
    """W3-C7 · demo schema tree when wave_ext source id is not in phase6 store."""
    return [
        {"id": f"sch-demo-public-{source_id}", "source_id": source_id, "name": "public",
         "description": "演示路径 · 默认 schema", "table_count": 3},
        {"id": f"sch-demo-analytics-{source_id}", "source_id": source_id, "name": "analytics",
         "description": "演示路径 · analytics", "table_count": 1},
    ]


def _demo_tables(source_id: str, schema_name: str) -> list[dict[str, Any]]:
    if schema_name == "analytics":
        names = ["events"]
    else:
        names = ["orders", "customers", "order_items"]
    return [
        {"id": f"tbl-demo-{schema_name}-{n}", "source_id": source_id, "schema_name": schema_name,
         "name": n, "row_count": 1000 + i * 200, "size_bytes": 256000, "description": f"demo {n}"}
        for i, n in enumerate(names)
    ]


def _demo_columns(source_id: str, schema_name: str, table_name: str) -> list[dict[str, Any]]:
    specs: dict[str, list[tuple[str, str, bool, bool]]] = {
        "orders": [("order_id", "BIGINT", False, True), ("customer_id", "BIGINT", False, False),
                   ("amount", "DECIMAL", True, False), ("status", "VARCHAR", True, False)],
        "customers": [("customer_id", "BIGINT", False, True), ("name", "VARCHAR", False, False),
                      ("email", "VARCHAR", True, False)],
        "order_items": [("item_id", "BIGINT", False, True), ("order_id", "BIGINT", False, False),
                        ("qty", "INT", False, False)],
        "events": [("event_id", "BIGINT", False, True), ("ts", "TIMESTAMP", False, False),
                   ("payload", "JSON", True, False)],
    }
    cols = specs.get(table_name, [("id", "BIGINT", False, True), ("name", "VARCHAR", True, False)])
    return [
        {"id": f"col-demo-{table_name}-{c}", "source_id": source_id, "schema_name": schema_name,
         "table_name": table_name, "name": c, "datatype": dt, "nullable": nullable,
         "primary_key": pk, "default_value": "", "description": ""}
        for c, dt, nullable, pk in cols
    ]


@router.get("/sources/{source_id}/schemas")
async def list_schemas(source_id: str) -> dict[str, Any]:
    eng = get_engine()
    if eng.get_source(source_id) is None:
        items = _demo_schemas(source_id)
        return {"items": items, "count": len(items), "demo": True}
    items = eng.list_schemas(source_id)
    return {"items": [s.model_dump() for s in items], "count": len(items), "demo": False}


@router.get("/sources/{source_id}/schemas/{schema_name}/tables")
async def list_tables(source_id: str, schema_name: str) -> dict[str, Any]:
    eng = get_engine()
    if eng.get_source(source_id) is None:
        items = _demo_tables(source_id, schema_name)
        return {"items": items, "count": len(items), "demo": True}
    items = eng.list_tables(source_id, schema_name)
    return {"items": [t.model_dump() for t in items], "count": len(items), "demo": False}


@router.get("/sources/{source_id}/schemas/{schema_name}/tables/{table_name}/columns")
async def list_columns(source_id: str, schema_name: str, table_name: str) -> dict[str, Any]:
    eng = get_engine()
    if eng.get_source(source_id) is None:
        items = _demo_columns(source_id, schema_name, table_name)
        return {"items": items, "count": len(items), "demo": True}
    items = eng.list_columns(source_id, schema_name, table_name)
    return {"items": [c.model_dump() for c in items], "count": len(items), "demo": False}


@router.get("/sources/{source_id}/schemas/{schema_name}/tables/{table_name}/foreign-keys")
async def list_foreign_keys(source_id: str, schema_name: str, table_name: str) -> dict[str, Any]:
    eng = get_engine()
    if eng.get_source(source_id) is None:
        items: list[dict[str, Any]] = []
        if table_name == "orders":
            items = [{
                "id": f"fk-demo-{table_name}", "source_id": source_id, "schema_name": schema_name,
                "table_name": table_name, "column_name": "customer_id",
                "ref_schema": schema_name, "ref_table": "customers", "ref_column": "customer_id",
            }]
        return {"items": items, "count": len(items), "demo": True}
    items = eng.list_foreign_keys(source_id, schema_name, table_name)
    return {"items": [fk.model_dump() for fk in items], "count": len(items), "demo": False}


@router.post("/sources/{source_id}/preview")
async def preview_data(source_id: str, req: PreviewRequest) -> dict[str, Any]:
    eng = get_engine()
    try:
        result = eng.preview_data(source_id, schema_name=req.schema_name, table_name=req.table_name, limit=req.limit)
        result["demo"] = False
        return result
    except KeyError:
        cols = [c["name"] for c in _demo_columns(source_id, req.schema_name or "public", req.table_name or "orders")]
        if not cols:
            cols = ["id", "name", "value"]
        rows = []
        for i in range(min(req.limit, 8)):
            row: dict[str, Any] = {}
            for c in cols:
                row[c] = i + 1 if c.endswith("_id") or c == "id" else f"{c}_{i}"
            rows.append(row)
        return {
            "source_id": source_id,
            "schema": req.schema_name,
            "table": req.table_name,
            "columns": cols,
            "rows": rows,
            "total": len(rows),
            "returned": len(rows),
            "demo": True,
        }


@router.get("/sources/{source_id}/capabilities")
async def get_source_capabilities(source_id: str) -> dict[str, Any]:
    eng = get_engine()
    try:
        caps = eng.get_source_capabilities(source_id)
        return {"source_id": source_id, "capabilities": caps}
    except KeyError:
        raise HTTPException(404, f"Source {source_id} not found")
