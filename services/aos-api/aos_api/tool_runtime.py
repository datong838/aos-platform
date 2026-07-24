"""T3.7 Tool runtime — real invoke for registry tools (TX OS substance)."""
from __future__ import annotations

from typing import Any

from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api import mock_data

log = get_logger("aos-api.tool_runtime")

KNOWN = {
    "query.objects": "Query",
    "fn.echo": "Function",
    "action.close": "Action",
    "wiki.read": "Wiki",
}


def invoke_tool(tool_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    if tool_id not in KNOWN:
        raise ApiError(code="NOT_FOUND", message=f"tool {tool_id} unknown", status_code=404)

    if tool_id == "query.objects":
        object_type = str(payload.get("objectType") or "WorkOrder")
        # Prefer PG when available; fallback mock
        try:
            with connect() as conn:
                rows = conn.execute(
                    "SELECT object_id, props FROM obj_instance WHERE object_type=%s ORDER BY object_id LIMIT 20",
                    (object_type,),
                ).fetchall()
            items = [
                {"id": r["object_id"], "type": object_type, **(r["props"] or {})} for r in rows
            ]
            result = {"items": items, "total": len(items), "source": "pg"}
        except Exception as exc:  # noqa: BLE001
            log.warning("tool_query_pg_fallback err=%s", exc)
            result = mock_data.query_objects(filters=payload.get("filters") or [], page=1, page_size=20)
            result["source"] = "mock"
        log.info("tool_invoke id=%s items=%s", tool_id, result.get("total"))
        return {"toolId": tool_id, "ok": True, "kind": KNOWN[tool_id], "result": result}

    if tool_id == "fn.echo":
        return {
            "toolId": tool_id,
            "ok": True,
            "kind": KNOWN[tool_id],
            "result": {"echo": payload, "codeAccepted": True},
        }

    if tool_id == "wiki.read":
        ot = str(payload.get("objectType") or "WorkOrder")
        oid = str(payload.get("objectId") or "wo-1001")
        try:
            with connect() as conn:
                row = conn.execute(
                    "SELECT body FROM wiki_page WHERE object_type=%s AND object_id=%s",
                    (ot, oid),
                ).fetchone()
            body = row["body"] if row else None
        except Exception:  # noqa: BLE001
            body = None
        return {
            "toolId": tool_id,
            "ok": body is not None,
            "kind": KNOWN[tool_id],
            "result": {"objectType": ot, "objectId": oid, "body": body},
        }

    # action.close — never write; require Draft
    return {
        "toolId": tool_id,
        "ok": False,
        "kind": KNOWN[tool_id],
        "requiresDraft": True,
        "result": {"message": "Action tools must go through Draft/execute"},
    }
