"""Module variables store — Phase 1 Workshop backend.

Stores module-scoped variables (page state) with type grouping and usage tracking.

W1-A1: group_name 约定存作用域 page|app|global（Variables 页 Tab 过滤）；
默认值由 'default' 改为创建时归一化为 'page'。
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.module_identity import resolve_module_pk
from aos_api.tenant_scope import TenantScope

log = get_logger("aos-api.module_variables")

def ensure_schema() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS module_variable (
              id TEXT PRIMARY KEY,
              module_id TEXT NOT NULL,
              name TEXT NOT NULL,
              var_type TEXT NOT NULL DEFAULT 'string',
              group_name TEXT NOT NULL DEFAULT 'default',
              initial_value JSONB NOT NULL DEFAULT 'null'::jsonb,
              current_value JSONB NOT NULL DEFAULT 'null'::jsonb,
              description TEXT NOT NULL DEFAULT '',
              org_id TEXT NOT NULL DEFAULT 'dev-org',
              project_id TEXT NOT NULL DEFAULT 'dev-project',
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_mv_module
            ON module_variable(module_id, org_id, project_id)
            """
        )
        conn.commit()


def list_variables(scope: TenantScope, module_id: str) -> list[dict[str, Any]]:
    ensure_schema()
    with connect(scope) as conn:
        rows = conn.execute(
            """
            SELECT * FROM module_variable
             WHERE module_id=%s AND org_id=%s AND project_id=%s
             ORDER BY group_name, created_at
            """,
            (module_id, *scope.key),
        ).fetchall()
    return [_row(r) for r in rows]


def get_variable(
    scope: TenantScope, module_id: str, variable_id: str
) -> dict[str, Any] | None:
    ensure_schema()
    with connect(scope) as conn:
        row = conn.execute(
            "SELECT * FROM module_variable "
            "WHERE id=%s AND module_id=%s AND org_id=%s AND project_id=%s",
            (variable_id, module_id, *scope.key),
        ).fetchone()
    return _row(row) if row else None


def create_variable(
    scope: TenantScope, module_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    ensure_schema()
    vid = payload.get("id") or f"var-{uuid.uuid4().hex[:10]}"
    init = payload.get("initialValue", payload.get("initial_value"))
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        conn.execute(
            """
            INSERT INTO module_variable (
                id, module_id, name, var_type, group_name,
                initial_value, current_value, description, org_id, project_id, module_pk
            ) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s)
            """,
            (
                vid,
                module_id,
                payload.get("name") or "新变量",
                payload.get("varType") or payload.get("var_type") or "string",
                payload.get("group") or payload.get("group_name") or "page",
                json.dumps(init),
                json.dumps(init),
                payload.get("description") or "",
                *scope.key,
                module_pk,
            ),
        )
        conn.commit()
    return get_variable(scope, module_id, vid)  # type: ignore[return-value]


def update_variable(
    scope: TenantScope, module_id: str, variable_id: str, patch: dict[str, Any]
) -> dict[str, Any] | None:
    cur = get_variable(scope, module_id, variable_id)
    if not cur:
        return None
    name = patch.get("name", cur["name"])
    var_type = patch.get("varType", cur["varType"])
    group_name = patch.get("group", cur.get("group"))
    initial_value = patch.get("initialValue", cur.get("initialValue"))
    current_value = patch.get("currentValue", cur.get("currentValue"))
    description = patch.get("description", cur.get("description"))
    with connect(scope) as conn:
        conn.execute(
            """
            UPDATE module_variable SET
                name=%s, var_type=%s, group_name=%s,
                initial_value=%s::jsonb, current_value=%s::jsonb,
                description=%s, updated_at=NOW()
            WHERE id=%s AND module_id=%s AND org_id=%s AND project_id=%s
            """,
            (
                name,
                var_type,
                group_name,
                json.dumps(initial_value),
                json.dumps(current_value),
                description,
                variable_id,
                module_id,
                *scope.key,
            ),
        )
        conn.commit()
    return get_variable(scope, module_id, variable_id)


def delete_variable(scope: TenantScope, module_id: str, variable_id: str) -> bool:
    ensure_schema()
    with connect(scope) as conn:
        result = conn.execute(
            "DELETE FROM module_variable "
            "WHERE id=%s AND module_id=%s AND org_id=%s AND project_id=%s",
            (variable_id, module_id, *scope.key),
        )
        conn.commit()
        return result.rowcount > 0


def list_usage(
    scope: TenantScope, module_id: str, variable_id: str
) -> list[dict[str, Any]]:
    """Return simulated usage locations for a variable within a module.

    Scans widget instances and queries that reference the variable name.
    """
    from aos_api.module_queries import list_queries
    from aos_api.widget_instances import list_instances

    var = get_variable(scope, module_id, variable_id)
    if not var:
        return []
    name = var["name"]
    usages: list[dict[str, Any]] = []
    for wi in list_instances(scope, module_id):
        cfg_json = json.dumps(wi.get("config") or {})
        if name in cfg_json:
            usages.append(
                {
                    "type": "widget",
                    "id": wi["id"],
                    "title": wi.get("title") or wi["id"],
                    "field": "config",
                }
            )
    for q in list_queries(scope, module_id):
        stmt = q.get("statement") or ""
        if name in stmt:
            usages.append(
                {
                    "type": "query",
                    "id": q["id"],
                    "title": q.get("name") or q["id"],
                    "field": "statement",
                }
            )
    return usages


def _parse_jsonb(v: Any) -> Any:
    """Parse a jsonb value that may come back as str, bytes, or already-parsed."""
    if v is None:
        return None
    if isinstance(v, (dict, list, int, float, bool)):
        return v
    if isinstance(v, str):
        if v == "" or v == "null":
            return None
        try:
            return json.loads(v)
        except Exception:
            return v
    return v


def _row(r: dict[str, Any]) -> dict[str, Any]:
    init = _parse_jsonb(r.get("initial_value"))
    cur = _parse_jsonb(r.get("current_value"))
    return {
        "id": r["id"],
        "moduleId": r["module_id"],
        "name": r["name"],
        "varType": r.get("var_type") or "string",
        "group": r.get("group_name") or "default",
        "initialValue": init,
        "currentValue": cur,
        "description": r.get("description") or "",
        "createdAt": str(r.get("created_at", "")),
        "updatedAt": str(r.get("updated_at", "")),
    }
