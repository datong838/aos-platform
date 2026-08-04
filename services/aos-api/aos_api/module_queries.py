"""Module queries store — Phase 1 Workshop backend.

Stores query functions for a module (SQL/ObjectSet queries that feed widgets).
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.module_identity import resolve_module_pk
from aos_api.tenant_scope import TenantScope

log = get_logger("aos-api.module_queries")

def ensure_schema() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS module_query (
              id TEXT PRIMARY KEY,
              module_id TEXT NOT NULL,
              name TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              query_type TEXT NOT NULL DEFAULT 'sql',
              source TEXT NOT NULL DEFAULT '',
              statement TEXT NOT NULL DEFAULT '',
              params JSONB NOT NULL DEFAULT '[]'::jsonb,
              enabled BOOLEAN NOT NULL DEFAULT TRUE,
              org_id TEXT NOT NULL DEFAULT 'dev-org',
              project_id TEXT NOT NULL DEFAULT 'dev-project',
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_mq_module
            ON module_query(module_id, org_id, project_id)
            """
        )
        conn.commit()


def list_queries(scope: TenantScope, module_id: str) -> list[dict[str, Any]]:
    ensure_schema()
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        rows = (
            conn.execute(
                "SELECT * FROM module_query "
                "WHERE module_pk=%s AND org_id=%s AND project_id=%s "
                "ORDER BY created_at",
                (module_pk, *scope.key),
            ).fetchall()
            if module_pk is not None
            else []
        )
    return [_row(r) for r in rows]


def get_query(
    scope: TenantScope, module_id: str, query_id: str
) -> dict[str, Any] | None:
    ensure_schema()
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        row = (
            conn.execute(
                "SELECT * FROM module_query "
                "WHERE id=%s AND module_pk=%s AND org_id=%s AND project_id=%s",
                (query_id, module_pk, *scope.key),
            ).fetchone()
            if module_pk is not None
            else None
        )
    return _row(row) if row else None


def create_query(
    scope: TenantScope, module_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    ensure_schema()
    qid = payload.get("id") or f"q-{uuid.uuid4().hex[:10]}"
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        conn.execute(
            """
            INSERT INTO module_query (
                id, module_id, name, description, query_type, source,
                statement, params, enabled, org_id, project_id, module_pk
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
            """,
            (
                qid,
                module_id,
                payload.get("name") or "新查询",
                payload.get("description") or "",
                payload.get("queryType") or payload.get("query_type") or "sql",
                payload.get("source") or "",
                payload.get("statement") or "",
                json.dumps(payload.get("params") or []),
                bool(payload.get("enabled", True)),
                *scope.key,
                module_pk,
            ),
        )
        conn.commit()
    return get_query(scope, module_id, qid)  # type: ignore[return-value]


def delete_query(scope: TenantScope, module_id: str, query_id: str) -> bool:
    ensure_schema()
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        if module_pk is None:
            return False
        result = conn.execute(
            "DELETE FROM module_query "
            "WHERE id=%s AND module_pk=%s AND org_id=%s AND project_id=%s",
            (query_id, module_pk, *scope.key),
        )
        conn.commit()
        return result.rowcount > 0


def _row(r: dict[str, Any]) -> dict[str, Any]:
    params = r.get("params") or []
    if isinstance(params, str):
        params = json.loads(params) if params else []
    return {
        "id": r["id"],
        "moduleId": r["module_id"],
        "name": r["name"],
        "description": r.get("description") or "",
        "queryType": r.get("query_type") or "sql",
        "source": r.get("source") or "",
        "statement": r.get("statement") or "",
        "params": params,
        "enabled": bool(r.get("enabled", True)),
        "createdAt": str(r.get("created_at", "")),
        "updatedAt": str(r.get("updated_at", "")),
    }
