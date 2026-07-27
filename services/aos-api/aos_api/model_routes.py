"""Phase 2 · Model Routes — task-type based routing rules.

Maps a task type (default / code-gen / vision / fallback) to a primary and
fallback registered model with an outbound network policy.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.model_routes")

_DEFAULT_ORG = "dev-org"
_DEFAULT_PROJECT = "dev-project"


def ensure_schema() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS model_route (
              id TEXT PRIMARY KEY,
              task_type TEXT NOT NULL,
              primary_model TEXT NOT NULL,
              fallback_model TEXT NOT NULL DEFAULT '',
              outbound_policy TEXT NOT NULL DEFAULT 'deny_public',
              priority INTEGER NOT NULL DEFAULT 100,
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
            CREATE UNIQUE INDEX IF NOT EXISTS uq_model_route_task
            ON model_route (org_id, project_id, task_type)
            """
        )
        conn.commit()


def list_routes(*, task_type: str | None = None) -> list[dict[str, Any]]:
    ensure_schema()
    clauses = ["org_id=%s", "project_id=%s"]
    params: list[Any] = [_DEFAULT_ORG, _DEFAULT_PROJECT]
    if task_type:
        clauses.append("task_type=%s")
        params.append(task_type)
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM model_route WHERE "
            + " AND ".join(clauses)
            + " ORDER BY priority, created_at",
            tuple(params),
        ).fetchall()
    return [_row(r) for r in rows]


def get_route(route_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM model_route WHERE id=%s AND org_id=%s AND project_id=%s",
            (route_id, _DEFAULT_ORG, _DEFAULT_PROJECT),
        ).fetchone()
    return _row(row) if row else None


def upsert_route(payload: dict[str, Any]) -> dict[str, Any]:
    """Upsert by id (if provided) or by task_type."""
    ensure_schema()
    rid = payload.get("id") or f"mr-{uuid.uuid4().hex[:8]}"
    with connect() as conn:
        # If no id but task_type exists, reuse that row
        if not payload.get("id"):
            existing = conn.execute(
                "SELECT id FROM model_route WHERE org_id=%s AND project_id=%s AND task_type=%s",
                (_DEFAULT_ORG, _DEFAULT_PROJECT, payload["taskType"]),
            ).fetchone()
            if existing:
                rid = existing["id"]
        conn.execute(
            """
            INSERT INTO model_route (
                id, task_type, primary_model, fallback_model, outbound_policy,
                priority, enabled, org_id, project_id
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
                task_type=EXCLUDED.task_type, primary_model=EXCLUDED.primary_model,
                fallback_model=EXCLUDED.fallback_model, outbound_policy=EXCLUDED.outbound_policy,
                priority=EXCLUDED.priority, enabled=EXCLUDED.enabled, updated_at=NOW()
            """,
            (
                rid,
                payload["taskType"],
                payload["primaryModel"],
                payload.get("fallbackModel") or "",
                payload.get("outboundPolicy") or "deny_public",
                int(payload.get("priority") or 100),
                bool(payload.get("enabled", True)),
                _DEFAULT_ORG,
                _DEFAULT_PROJECT,
            ),
        )
        conn.commit()
    return get_route(rid)  # type: ignore[return-value]


def delete_route(route_id: str) -> bool:
    ensure_schema()
    with connect() as conn:
        result = conn.execute(
            "DELETE FROM model_route WHERE id=%s AND org_id=%s AND project_id=%s",
            (route_id, _DEFAULT_ORG, _DEFAULT_PROJECT),
        )
        conn.commit()
        return result.rowcount > 0


def _row(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": r["id"],
        "taskType": r["task_type"],
        "primaryModel": r["primary_model"],
        "fallbackModel": r.get("fallback_model") or "",
        "outboundPolicy": r.get("outbound_policy") or "deny_public",
        "priority": int(r.get("priority") or 100),
        "enabled": bool(r.get("enabled", True)),
        "createdAt": str(r.get("created_at", "")),
        "updatedAt": str(r.get("updated_at", "")),
    }
