"""Widget catalog store — Phase 1 Workshop backend.

Widget registry catalog: builtin + marketplace + custom widgets.
Distinct from widget_instances (per-module placements) and widget_registry (plugin installs).
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.tenant_scope import TenantScope

log = get_logger("aos-api.widget_catalog")

__schema_ensured = False

def ensure_schema() -> None:
    global __schema_ensured
    if __schema_ensured:
        return
    try:
        with connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS widget_catalog (
                  id TEXT NOT NULL,
                  name TEXT NOT NULL,
                  name_zh TEXT NOT NULL DEFAULT '',
                  type TEXT NOT NULL DEFAULT 'unknown',
                  source TEXT NOT NULL DEFAULT 'builtin',
                  category TEXT NOT NULL DEFAULT 'general',
                  icon TEXT NOT NULL DEFAULT '',
                  description TEXT NOT NULL DEFAULT '',
                  config_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
                  version TEXT NOT NULL DEFAULT '1.0.0',
                  installed BOOLEAN NOT NULL DEFAULT TRUE,
                  org_id TEXT NOT NULL DEFAULT 'dev-org',
                  project_id TEXT NOT NULL DEFAULT 'dev-project',
                  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                  PRIMARY KEY (org_id, project_id, id)
                )
                """
            )
            conn.commit()
        __schema_ensured = True
    except Exception:
        # Table likely already exists; mark as ensured to avoid retrying on every request
        __schema_ensured = True


def list_widgets(
    scope: TenantScope, source: str | None = None
) -> list[dict[str, Any]]:
    ensure_schema()
    with connect(scope) as conn:
        if source:
            rows = conn.execute(
                """
                SELECT * FROM widget_catalog
                 WHERE source=%s AND org_id=%s AND project_id=%s
                 ORDER BY created_at
                """,
                (source, *scope.key),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM widget_catalog
                 WHERE org_id=%s AND project_id=%s
                 ORDER BY source, created_at
                """,
                scope.key,
            ).fetchall()
    return [_row(r) for r in rows]


def get_widget(scope: TenantScope, widget_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect(scope) as conn:
        row = conn.execute(
            "SELECT * FROM widget_catalog "
            "WHERE id=%s AND org_id=%s AND project_id=%s",
            (widget_id, *scope.key),
        ).fetchone()
    return _row(row) if row else None


def create_widget(scope: TenantScope, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_schema()
    wid = payload.get("id") or f"w-{uuid.uuid4().hex[:10]}"
    with connect(scope) as conn:
        result = conn.execute(
            """
            INSERT INTO widget_catalog (
                id, name, name_zh, type, source, category, icon, description,
                config_schema, version, installed, org_id, project_id
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
            ON CONFLICT (org_id, project_id, id) DO NOTHING
            """,
            (
                wid,
                payload.get("name") or wid,
                payload.get("nameZh") or payload.get("name_zh") or "",
                payload.get("type") or "unknown",
                payload.get("source") or "builtin",
                payload.get("category") or "general",
                payload.get("icon") or "",
                payload.get("description") or "",
                json.dumps(payload.get("configSchema") or payload.get("config_schema") or {}),
                payload.get("version") or "1.0.0",
                bool(payload.get("installed", True)),
                *scope.key,
            ),
        )
        conn.commit()
    if result.rowcount == 0:
        raise PermissionError("widget belongs to another tenant or already exists")
    return get_widget(scope, wid)  # type: ignore[return-value]


def _row(r: dict[str, Any]) -> dict[str, Any]:
    schema = r.get("config_schema") or {}
    if isinstance(schema, str):
        schema = json.loads(schema) if schema else {}
    return {
        "id": r["id"],
        "name": r["name"],
        "nameZh": r.get("name_zh") or "",
        "type": r.get("type") or "unknown",
        "source": r.get("source") or "builtin",
        "category": r.get("category") or "general",
        "icon": r.get("icon") or "",
        "description": r.get("description") or "",
        "configSchema": schema,
        "version": r.get("version") or "1.0.0",
        "installed": bool(r.get("installed", True)),
        "createdAt": str(r.get("created_at", "")),
        "updatedAt": str(r.get("updated_at", "")),
    }
