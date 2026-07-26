"""Module queries store — Phase 1 Workshop backend.

Stores query functions for a module (SQL/ObjectSet queries that feed widgets).
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.module_queries")

_DEFAULT_ORG = "dev-org"
_DEFAULT_PROJECT = "dev-project"


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


def list_queries(module_id: str) -> list[dict[str, Any]]:
    ensure_schema()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM module_query
             WHERE module_id=%s AND org_id=%s AND project_id=%s
             ORDER BY created_at
            """,
            (module_id, _DEFAULT_ORG, _DEFAULT_PROJECT),
        ).fetchall()
    return [_row(r) for r in rows]


def get_query(query_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM module_query WHERE id=%s",
            (query_id,),
        ).fetchone()
    return _row(row) if row else None


def create_query(module_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_schema()
    qid = payload.get("id") or f"q-{uuid.uuid4().hex[:10]}"
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO module_query (
                id, module_id, name, description, query_type, source,
                statement, params, enabled, org_id, project_id
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
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
                _DEFAULT_ORG,
                _DEFAULT_PROJECT,
            ),
        )
        conn.commit()
    return get_query(qid)  # type: ignore[return-value]


def delete_query(query_id: str) -> bool:
    ensure_schema()
    with connect() as conn:
        result = conn.execute(
            "DELETE FROM module_query WHERE id=%s", (query_id,)
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
