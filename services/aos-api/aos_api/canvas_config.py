"""Canvas config store — Phase 1 Workshop backend.

Stores the complete canvas configuration (layout tree + components) for a module.
"""
from __future__ import annotations

import json
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.module_identity import resolve_module_pk
from aos_api.schema_readiness import mark_relation_ready, relation_exists
from aos_api.tenant_scope import TenantScope

log = get_logger("aos-api.canvas_config")
def ensure_schema() -> None:
    if relation_exists("module_canvas_config"):
        return
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS module_canvas_config (
              module_id TEXT PRIMARY KEY,
              layout JSONB NOT NULL DEFAULT '{}'::jsonb,
              components JSONB NOT NULL DEFAULT '{}'::jsonb,
              version INTEGER NOT NULL DEFAULT 1,
              org_id TEXT NOT NULL DEFAULT 'dev-org',
              project_id TEXT NOT NULL DEFAULT 'dev-project',
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.commit()
    mark_relation_ready("module_canvas_config")


def get_config(scope: TenantScope, module_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        row = (
            conn.execute(
                "SELECT * FROM module_canvas_config "
                "WHERE module_pk=%s AND org_id=%s AND project_id=%s",
                (module_pk, *scope.key),
            ).fetchone()
            if module_pk is not None
            else None
        )
    if not row:
        return None
    return _row(row)


def put_config(
    scope: TenantScope, module_id: str, layout: dict, components: dict
) -> dict[str, Any]:
    ensure_schema()
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        if module_pk is None:
            raise PermissionError("module canvas parent is unavailable in tenant scope")
        result = conn.execute(
            """
            INSERT INTO module_canvas_config (
                module_id, layout, components, version, org_id, project_id, module_pk
            ) VALUES (%s, %s::jsonb, %s::jsonb, 1, %s, %s, %s)
            ON CONFLICT (org_id, project_id, module_pk) DO UPDATE SET
                layout = EXCLUDED.layout,
                components = EXCLUDED.components,
                version = module_canvas_config.version + 1,
                module_pk = COALESCE(module_canvas_config.module_pk, EXCLUDED.module_pk),
                updated_at = NOW()
            WHERE module_canvas_config.org_id=EXCLUDED.org_id
              AND module_canvas_config.project_id=EXCLUDED.project_id
            """,
            (
                module_id,
                json.dumps(layout),
                json.dumps(components),
                *scope.key,
                module_pk,
            ),
        )
        conn.commit()
    if result.rowcount == 0:
        raise PermissionError("module canvas belongs to another tenant")
    return get_config(scope, module_id)  # type: ignore[return-value]


def _row(r: dict[str, Any]) -> dict[str, Any]:
    layout = r.get("layout") or {}
    if isinstance(layout, str):
        layout = json.loads(layout) if layout else {}
    comps = r.get("components") or {}
    if isinstance(comps, str):
        comps = json.loads(comps) if comps else {}
    return {
        "moduleId": r["module_id"],
        "layout": layout,
        "components": comps,
        "version": int(r.get("version", 1)),
        "updatedAt": str(r.get("updated_at", "")),
    }
