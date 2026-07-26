"""Module interface store — Phase 1 Workshop backend.

Stores module API/interface definitions (entry params, expose config).
"""
from __future__ import annotations

import json
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.module_interfaces")

_DEFAULT_ORG = "dev-org"
_DEFAULT_PROJECT = "dev-project"


def ensure_schema() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS module_interface (
              module_id TEXT PRIMARY KEY,
              name TEXT NOT NULL DEFAULT '',
              description TEXT NOT NULL DEFAULT '',
              entry_params JSONB NOT NULL DEFAULT '[]'::jsonb,
              expose JSONB NOT NULL DEFAULT '{}'::jsonb,
              version TEXT NOT NULL DEFAULT '1.0.0',
              org_id TEXT NOT NULL DEFAULT 'dev-org',
              project_id TEXT NOT NULL DEFAULT 'dev-project',
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.commit()


def get_interface(module_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM module_interface
             WHERE module_id=%s AND org_id=%s AND project_id=%s
            """,
            (module_id, _DEFAULT_ORG, _DEFAULT_PROJECT),
        ).fetchone()
    return _row(row) if row else None


def put_interface(
    module_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    ensure_schema()
    name = payload.get("name") or ""
    description = payload.get("description") or ""
    entry_params = payload.get("entryParams") or payload.get("entry_params") or []
    expose = payload.get("expose") or {}
    version = payload.get("version") or "1.0.0"
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO module_interface (
                module_id, name, description, entry_params, expose,
                version, org_id, project_id
            ) VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)
            ON CONFLICT (module_id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                entry_params = EXCLUDED.entry_params,
                expose = EXCLUDED.expose,
                version = EXCLUDED.version,
                updated_at = NOW()
            """,
            (
                module_id,
                name,
                description,
                json.dumps(entry_params),
                json.dumps(expose),
                version,
                _DEFAULT_ORG,
                _DEFAULT_PROJECT,
            ),
        )
        conn.commit()
    return get_interface(module_id)  # type: ignore[return-value]


def _row(r: dict[str, Any]) -> dict[str, Any]:
    ep = r.get("entry_params") or []
    if isinstance(ep, str):
        ep = json.loads(ep) if ep else []
    ex = r.get("expose") or {}
    if isinstance(ex, str):
        ex = json.loads(ex) if ex else {}
    return {
        "moduleId": r["module_id"],
        "name": r.get("name") or "",
        "description": r.get("description") or "",
        "entryParams": ep,
        "expose": ex,
        "version": r.get("version") or "1.0.0",
        "updatedAt": str(r.get("updated_at", "")),
    }
