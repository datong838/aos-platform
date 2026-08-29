"""Widget instances store — Phase 1 Workshop backend.

Stores widget instances placed on a module canvas (component instances, not registry).
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.module_identity import resolve_module_pk
from aos_api.schema_readiness import mark_relation_ready, relation_exists
from aos_api.tenant_scope import TenantScope

log = get_logger("aos-api.widget_instances")
def ensure_schema() -> None:
    if relation_exists("module_widget_instance"):
        return
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS module_widget_instance (
              id TEXT PRIMARY KEY,
              module_id TEXT NOT NULL,
              widget_id TEXT NOT NULL,
              type TEXT NOT NULL,
              title TEXT NOT NULL DEFAULT '',
              config JSONB NOT NULL DEFAULT '{}'::jsonb,
              layout JSONB NOT NULL DEFAULT '{}'::jsonb,
              sort_order INTEGER NOT NULL DEFAULT 0,
              org_id TEXT NOT NULL DEFAULT 'dev-org',
              project_id TEXT NOT NULL DEFAULT 'dev-project',
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_mwi_module
            ON module_widget_instance(module_id, org_id, project_id)
            """
        )
        conn.commit()
    mark_relation_ready("module_widget_instance")


def list_instances(scope: TenantScope, module_id: str) -> list[dict[str, Any]]:
    ensure_schema()
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        rows = (
            conn.execute(
                "SELECT * FROM module_widget_instance "
                "WHERE module_pk=%s AND org_id=%s AND project_id=%s "
                "ORDER BY sort_order, created_at",
                (module_pk, *scope.key),
            ).fetchall()
            if module_pk is not None
            else []
        )
    return [_row(r) for r in rows]


def get_instance(
    scope: TenantScope, module_id: str, instance_id: str
) -> dict[str, Any] | None:
    ensure_schema()
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        row = (
            conn.execute(
                "SELECT * FROM module_widget_instance "
                "WHERE id=%s AND module_pk=%s AND org_id=%s AND project_id=%s",
                (instance_id, module_pk, *scope.key),
            ).fetchone()
            if module_pk is not None
            else None
        )
    return _row(row) if row else None


def create_instance(
    scope: TenantScope, module_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    ensure_schema()
    iid = payload.get("id") or f"wi-{uuid.uuid4().hex[:10]}"
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        conn.execute(
            """
            INSERT INTO module_widget_instance (
                id, module_id, widget_id, type, title, config, layout,
                sort_order, org_id, project_id, module_pk
            ) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s)
            """,
            (
                iid,
                module_id,
                payload.get("widgetId") or payload.get("widget_id") or "",
                payload.get("type") or "unknown",
                payload.get("title") or "",
                json.dumps(payload.get("config") or {}),
                json.dumps(payload.get("layout") or {}),
                int(payload.get("sortOrder") or payload.get("sort_order") or 0),
                *scope.key,
                module_pk,
            ),
        )
        conn.commit()
    return get_instance(scope, module_id, iid)  # type: ignore[return-value]


def update_instance(
    scope: TenantScope, module_id: str, instance_id: str, patch: dict[str, Any]
) -> dict[str, Any] | None:
    cur = get_instance(scope, module_id, instance_id)
    if not cur:
        return None
    title = patch.get("title", cur["title"])
    config = patch.get("config", cur["config"])
    layout = patch.get("layout", cur["layout"])
    sort_order = patch.get("sortOrder", cur.get("sortOrder", 0))
    widget_id = patch.get("widgetId", cur.get("widgetId", ""))
    type_ = patch.get("type", cur.get("type", "unknown"))
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        if module_pk is None:
            return None
        conn.execute(
            """
            UPDATE module_widget_instance SET
                title=%s, config=%s::jsonb, layout=%s::jsonb,
                sort_order=%s, widget_id=%s, type=%s, updated_at=NOW()
            WHERE id=%s AND module_pk=%s AND org_id=%s AND project_id=%s
            """,
            (
                title,
                json.dumps(config),
                json.dumps(layout),
                sort_order,
                widget_id,
                type_,
                instance_id,
                module_pk,
                *scope.key,
            ),
        )
        conn.commit()
    return get_instance(scope, module_id, instance_id)


def delete_instance(scope: TenantScope, module_id: str, instance_id: str) -> bool:
    ensure_schema()
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        if module_pk is None:
            return False
        result = conn.execute(
            "DELETE FROM module_widget_instance "
            "WHERE id=%s AND module_pk=%s AND org_id=%s AND project_id=%s",
            (instance_id, module_pk, *scope.key),
        )
        conn.commit()
        return result.rowcount > 0


def _row(r: dict[str, Any]) -> dict[str, Any]:
    config = r.get("config") or {}
    if isinstance(config, str):
        config = json.loads(config) if config else {}
    layout = r.get("layout") or {}
    if isinstance(layout, str):
        layout = json.loads(layout) if layout else {}
    return {
        "id": r["id"],
        "moduleId": r["module_id"],
        "widgetId": r.get("widget_id") or "",
        "type": r.get("type") or "unknown",
        "title": r.get("title") or "",
        "config": config,
        "layout": layout,
        "sortOrder": int(r.get("sort_order", 0)),
        "createdAt": str(r.get("created_at", "")),
        "updatedAt": str(r.get("updated_at", "")),
    }
