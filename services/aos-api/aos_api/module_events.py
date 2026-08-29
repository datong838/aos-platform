"""Module Events persistence — Phase C 222plan.

Provides event binding CRUD for Workshop modules.
Events are stored in a dedicated PostgreSQL table.
"""
from __future__ import annotations

import json
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.module_identity import resolve_module_pk
from aos_api.schema_readiness import mark_relation_ready, relation_exists
from aos_api.tenant_scope import TenantScope

log = get_logger("aos-api.module_events")
_DEFAULT_EVENTS: list[dict[str, Any]] = [
    {
        "id": "evt-refresh",
        "name": "刷新数据",
        "trigger": {"type": "interval", "value": 30, "unit": "seconds"},
        "action": {"type": "query", "target": "object_table", "params": {}},
        "enabled": True,
    },
    {
        "id": "evt-selection-change",
        "name": "选择变更联动",
        "trigger": {"type": "on_select", "widgetId": ""},
        "action": {"type": "set_variable", "target": "selectedIds", "params": {}},
        "enabled": True,
    },
]


def ensure_events_schema() -> None:
    """Create module_events table if not exists."""
    if relation_exists("module_events"):
        return
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS module_events (
              id TEXT PRIMARY KEY,
              module_id TEXT NOT NULL,
              name TEXT NOT NULL,
              trigger_config JSONB NOT NULL DEFAULT '{}'::jsonb,
              action_config JSONB NOT NULL DEFAULT '{}'::jsonb,
              enabled BOOLEAN NOT NULL DEFAULT TRUE,
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
            CREATE INDEX IF NOT EXISTS idx_module_events_module
            ON module_events(module_id, org_id, project_id)
            """
        )
        conn.commit()
    mark_relation_ready("module_events")
    log.info("module_events_schema_ensured")


def seed_events_if_empty(scope: TenantScope, module_id: str) -> None:
    """Seed default events for a module if none exist."""
    ensure_events_schema()
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        if module_pk is None:
            return
        existing = conn.execute(
            """
            SELECT COUNT(*) as cnt FROM module_events
             WHERE module_pk = %s AND org_id = %s AND project_id = %s
            """,
            (module_pk, *scope.key),
        ).fetchone()
        if existing and existing["cnt"] > 0:
            return
        for i, evt in enumerate(_DEFAULT_EVENTS):
            eid = f"{module_id}-{evt['id']}"
            conn.execute(
                """
                INSERT INTO module_events (
                    id, module_id, name, trigger_config, action_config,
                    enabled, sort_order, org_id, project_id, module_pk
                ) VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s)
                ON CONFLICT (org_id, project_id, id) DO NOTHING
                """,
                (
                    eid,
                    module_id,
                    evt["name"],
                    json.dumps(evt["trigger"]),
                    json.dumps(evt["action"]),
                    evt["enabled"],
                    i,
                    *scope.key,
                    module_pk,
                ),
            )
        conn.commit()
    log.info("module_events_seeded module=%s count=%s", module_id, len(_DEFAULT_EVENTS))


def list_events(scope: TenantScope, module_id: str) -> list[dict[str, Any]]:
    """List all events for a module."""
    ensure_events_schema()
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        rows = (
            conn.execute(
                "SELECT * FROM module_events "
                "WHERE module_pk=%s AND org_id=%s AND project_id=%s "
                "ORDER BY sort_order, created_at",
                (module_pk, *scope.key),
            ).fetchall()
            if module_pk is not None
            else []
        )
    return [_row_to_event(r) for r in rows]


def get_event(
    scope: TenantScope, module_id: str, event_id: str
) -> dict[str, Any] | None:
    ensure_events_schema()
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        row = (
            conn.execute(
                "SELECT * FROM module_events "
                "WHERE id=%s AND module_pk=%s AND org_id=%s AND project_id=%s",
                (event_id, module_pk, *scope.key),
            ).fetchone()
            if module_pk is not None
            else None
        )
    return _row_to_event(row) if row else None


def create_event(
    scope: TenantScope, module_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Create a new event binding."""
    ensure_events_schema()
    import uuid

    eid = payload.get("id") or f"{module_id}-evt-{uuid.uuid4().hex[:8]}"
    name = payload.get("name") or "新事件"
    trigger = payload.get("trigger") or {}
    action = payload.get("action") or {}
    enabled = bool(payload.get("enabled", True))
    sort_order = int(payload.get("sortOrder") or payload.get("sort_order") or 0)

    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        conn.execute(
            """
            INSERT INTO module_events (
                id, module_id, name, trigger_config, action_config,
                enabled, sort_order, org_id, project_id, module_pk
            ) VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s)
            """,
            (
                eid,
                module_id,
                name,
                json.dumps(trigger),
                json.dumps(action),
                enabled,
                sort_order,
                *scope.key,
                module_pk,
            ),
        )
        conn.commit()
    log.info("module_event_created id=%s module=%s", eid, module_id)
    return get_event(scope, module_id, eid)  # type: ignore[return-value]


def update_event(
    scope: TenantScope, module_id: str, event_id: str, patch: dict[str, Any]
) -> dict[str, Any] | None:
    """Update an existing event binding."""
    cur = get_event(scope, module_id, event_id)
    if not cur:
        return None

    name = patch.get("name", cur["name"])
    trigger = patch.get("trigger", cur["trigger"])
    action = patch.get("action", cur["action"])
    enabled = patch.get("enabled", cur["enabled"])
    sort_order = patch.get("sortOrder", cur.get("sortOrder", 0))

    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        if module_pk is None:
            return None
        conn.execute(
            """
            UPDATE module_events SET
                name = %s,
                trigger_config = %s::jsonb,
                action_config = %s::jsonb,
                enabled = %s,
                sort_order = %s,
                updated_at = NOW()
            WHERE id=%s AND module_pk=%s AND org_id=%s AND project_id=%s
            """,
            (
                name,
                json.dumps(trigger),
                json.dumps(action),
                enabled,
                sort_order,
                event_id,
                module_pk,
                *scope.key,
            ),
        )
        conn.commit()
    return get_event(scope, module_id, event_id)


def delete_event(scope: TenantScope, module_id: str, event_id: str) -> bool:
    """Delete an event binding. Returns True if deleted."""
    ensure_events_schema()
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        if module_pk is None:
            return False
        result = conn.execute(
            "DELETE FROM module_events "
            "WHERE id=%s AND module_pk=%s AND org_id=%s AND project_id=%s",
            (event_id, module_pk, *scope.key),
        )
        conn.commit()
        deleted = result.rowcount > 0
    if deleted:
        log.info("module_event_deleted id=%s", event_id)
    return deleted


def list_triggers_catalog() -> list[dict[str, Any]]:
    """Return the catalog of available trigger types."""
    return [
        {"type": "on_click", "label": "点击", "description": "Widget 被点击时触发", "params": ["widgetId"]},
        {"type": "on_select", "label": "选择变更", "description": "行/对象被选中时触发", "params": ["widgetId"]},
        {"type": "on_change", "label": "值变更", "description": "输入值变化时触发", "params": ["variableId"]},
        {"type": "on_load", "label": "页面加载", "description": "页面加载完成时触发", "params": []},
        {"type": "interval", "label": "定时轮询", "description": "按时间间隔触发", "params": ["value", "unit"]},
        {"type": "custom", "label": "自定义", "description": "自定义触发条件", "params": ["expression"]},
    ]


def list_actions_catalog() -> list[dict[str, Any]]:
    """Return the catalog of available action types."""
    return [
        {"type": "query", "label": "执行查询", "description": "执行 SQL/ObjectSet 查询", "params": ["target"]},
        {"type": "set_variable", "label": "设置变量", "description": "更新变量值", "params": ["target"]},
        {"type": "navigate", "label": "页面跳转", "description": "导航到另一个页面", "params": ["target"]},
        {"type": "call_function", "label": "调用函数", "description": "执行 AIP Logic 函数", "params": ["target"]},
        {"type": "show_notification", "label": "显示通知", "description": "弹窗或 toast 提示", "params": []},
        {"type": "open_overlay", "label": "打开浮层", "description": "弹出 Overlay/Modal", "params": ["target"]},
        {"type": "export_data", "label": "导出数据", "description": "导出当前数据集", "params": []},
    ]


def _row_to_event(r: dict[str, Any]) -> dict[str, Any]:
    trigger = r["trigger_config"]
    if not isinstance(trigger, dict):
        trigger = json.loads(trigger) if trigger else {}
    action = r["action_config"]
    if not isinstance(action, dict):
        action = json.loads(action) if action else {}
    return {
        "id": r["id"],
        "moduleId": r["module_id"],
        "name": r["name"],
        "trigger": trigger,
        "action": action,
        "enabled": bool(r["enabled"]),
        "sortOrder": int(r.get("sort_order", 0)),
        "createdAt": str(r.get("created_at", "")),
        "updatedAt": str(r.get("updated_at", "")),
    }
