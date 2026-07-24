from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.marking import apply_field_redaction, can_access_object
from aos_api import mock_data

router = APIRouter(tags=["object-sets"])
log = get_logger("aos-api.object_sets")


def _prop_defs(object_type: str) -> list:
    try:
        with connect() as conn:
            row = conn.execute(
                "SELECT properties FROM meta_object_type WHERE id=%s",
                (object_type,),
            ).fetchone()
        if not row:
            return []
        props = row["properties"]
        return list(props) if isinstance(props, list) else []
    except Exception:  # noqa: BLE001
        return []


class ObjectSetQuery(BaseModel):
    filters: list[dict[str, Any]] = Field(default_factory=list)
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=50, ge=1, le=1000)
    objectType: str = "WorkOrder"
    source: str = Field(default="pg", description="pg|mock")


def _query_pg(
    *,
    object_type: str,
    filters: list[dict[str, Any]],
    page: int,
    page_size: int,
) -> dict[str, Any]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT object_id, props FROM obj_instance WHERE object_type=%s ORDER BY object_id",
            (object_type,),
        ).fetchall()
    items: list[dict[str, Any]] = [
        {"id": r["object_id"], "type": object_type, **(r["props"] or {})} for r in rows
    ]
    for f in filters:
        field = f.get("field")
        value = f.get("value")
        if field and value is not None:
            items = [i for i in items if str(i.get(field)) == str(value)]
    total = len(items)
    start = max(page - 1, 0) * page_size
    page_rows = items[start : start + page_size]
    log.info(
        "object_sets_query_pg type=%s filters=%s total=%s",
        object_type,
        len(filters),
        total,
    )
    return {
        "items": page_rows,
        "page": page,
        "pageSize": page_size,
        "total": total,
        "selectionLimit": 10,
        "source": "pg",
    }


@router.post("/v1/object-sets/query")
def object_sets_query(
    body: ObjectSetQuery,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    if len(body.filters) > 10:
        raise ApiError(
            code="VALIDATION",
            message="filters exceed 10 dimensions (Selection limit)",
            status_code=400,
            details={"maxFilters": 10, "got": len(body.filters)},
        )
    if body.source == "mock":
        try:
            result = mock_data.query_objects(
                filters=body.filters,
                page=body.page,
                page_size=body.pageSize,
            )
        except ValueError as exc:
            raise ApiError(code="VALIDATION", message=str(exc), status_code=400) from exc
        result["source"] = "mock"
    else:
        try:
            result = _query_pg(
                object_type=body.objectType,
                filters=body.filters,
                page=body.page,
                page_size=body.pageSize,
            )
        except Exception as exc:
            log.exception("pg_query_failed_fallback_mock")
            result = mock_data.query_objects(
                filters=body.filters,
                page=body.page,
                page_size=body.pageSize,
            )
            result["source"] = "mock-fallback"
            result["fallbackReason"] = str(exc)
    log.info(
        "object_sets_query org=%s total=%s source=%s",
        principal.org_id,
        result["total"],
        result.get("source"),
    )
    prop_defs = _prop_defs(body.objectType)
    if result.get("items"):
        with connect() as conn:
            kept: list[dict[str, Any]] = []
            for it in result["items"]:
                oid = str(it.get("id") or "")
                if not oid or not can_access_object(principal, conn, body.objectType, oid):
                    continue
                if prop_defs:
                    kept.append(
                        apply_field_redaction(principal, dict(it), prop_defs, conn=conn)
                    )
                else:
                    kept.append(dict(it))
        result["items"] = kept
        result["total"] = len(kept)
    return result
