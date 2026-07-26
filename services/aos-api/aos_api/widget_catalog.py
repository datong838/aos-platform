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

log = get_logger("aos-api.widget_catalog")

_DEFAULT_ORG = "dev-org"
_DEFAULT_PROJECT = "dev-project"


def ensure_schema() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS widget_catalog (
              id TEXT PRIMARY KEY,
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
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.commit()


def list_widgets(source: str | None = None) -> list[dict[str, Any]]:
    ensure_schema()
    with connect() as conn:
        if source:
            rows = conn.execute(
                """
                SELECT * FROM widget_catalog
                 WHERE source=%s AND org_id=%s AND project_id=%s
                 ORDER BY created_at
                """,
                (source, _DEFAULT_ORG, _DEFAULT_PROJECT),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM widget_catalog
                 WHERE org_id=%s AND project_id=%s
                 ORDER BY source, created_at
                """,
                (_DEFAULT_ORG, _DEFAULT_PROJECT),
            ).fetchall()
    return [_row(r) for r in rows]


def get_widget(widget_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM widget_catalog WHERE id=%s",
            (widget_id,),
        ).fetchone()
    return _row(row) if row else None


def create_widget(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_schema()
    wid = payload.get("id") or f"w-{uuid.uuid4().hex[:10]}"
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO widget_catalog (
                id, name, name_zh, type, source, category, icon, description,
                config_schema, version, installed, org_id, project_id
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
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
                _DEFAULT_ORG,
                _DEFAULT_PROJECT,
            ),
        )
        conn.commit()
    return get_widget(wid)  # type: ignore[return-value]


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
