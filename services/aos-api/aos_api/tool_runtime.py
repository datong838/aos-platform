"""T3.7 Tool runtime — real invoke for registry tools (TX OS substance)."""

from __future__ import annotations

from typing import Any

from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.tenant_scope import TenantScope

log = get_logger("aos-api.tool_runtime")

KNOWN = {
    "query.objects": "Query",
    "fn.echo": "Function",
    "action.close": "Action",
    "wiki.read": "Wiki",
}


def invoke_tool(
    scope: TenantScope, tool_id: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    payload = payload or {}
    if tool_id.startswith("cap."):
        from aos_api.aip_capability_binding_service import AipCapabilityBindingService
        from aos_api.aip_capability_tool_exits import (
            capability_id_from_tool,
            invoke_capability_tool,
        )

        cid = capability_id_from_tool(tool_id)
        binding_dict = None
        if cid:
            try:
                for row in AipCapabilityBindingService().list_bindings(scope, limit=200):
                    dump = row.model_dump(by_alias=True) if hasattr(row, "model_dump") else dict(row)
                    cap = dump.get("capability") or {}
                    if str(cap.get("assetId") or "") == cid:
                        binding_dict = dump
                        break
            except Exception:
                binding_dict = None
        return invoke_capability_tool(tool_id, binding=binding_dict, payload=payload)

    if tool_id == "fn.echo" or tool_id.startswith("fn.logic."):
        from aos_api.aip_function_tool_exits import invoke_function_tool

        return invoke_function_tool(tool_id, payload=payload)

    if tool_id not in KNOWN:
        raise ApiError(
            code="NOT_FOUND", message=f"tool {tool_id} unknown", status_code=404
        )

    if tool_id == "query.objects":
        object_type = str(payload.get("objectType") or "WorkOrder")
        # 只走真实 PG；不再降级到 mock_data 假数据
        try:
            with connect(scope) as conn:
                rows = conn.execute(
                    "SELECT object_id, props FROM obj_instance WHERE object_type=%s "
                    "AND org_id=%s AND project_id=%s ORDER BY object_id LIMIT 20",
                    (object_type, *scope.key),
                ).fetchall()
            items = [
                {"id": r["object_id"], "type": object_type, **(r["props"] or {})}
                for r in rows
            ]
            result: dict[str, Any] = {
                "items": items,
                "total": len(items),
                "source": "pg",
            }
        except Exception as exc:  # noqa: BLE001
            # TODO(持久化改造): PG 不可用时不再降级到 mock 假数据；真实数据库高可用待补齐
            log.warning("tool_query_pg_failed err=%s", exc)
            raise ApiError(
                code="OBJECT_STORE",
                message=f"object query failed: {exc}",
                status_code=502,
            ) from exc
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
        ot = str(payload.get("objectType") or "").strip()
        oid = str(payload.get("objectId") or "").strip()
        if not ot or not oid:
            raise ApiError(
                code="AIP_INVALID_ARGUMENT",
                message="wiki.read requires exact objectType and objectId (demo wo-1001 disabled)",
                status_code=400,
            )
        if oid.lower() == "wo-1001":
            raise ApiError(
                code="AIP_INVALID_ARGUMENT",
                message="demo objectId wo-1001 is disabled",
                status_code=400,
            )
        try:
            with connect(scope) as conn:
                row = conn.execute(
                    "SELECT body FROM wiki_page WHERE object_type=%s AND object_id=%s "
                    "AND org_id=%s AND project_id=%s",
                    (ot, oid, *scope.key),
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
