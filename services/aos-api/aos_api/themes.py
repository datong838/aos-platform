"""Themes store — Phase 1 Workshop backend.

Stores theme presets (light/dark/high-contrast) with token maps.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.tenant_scope import TenantScope

log = get_logger("aos-api.themes")

def ensure_schema() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS theme (
              id TEXT NOT NULL,
              name TEXT NOT NULL,
              mode TEXT NOT NULL DEFAULT 'light',
              is_preset BOOLEAN NOT NULL DEFAULT FALSE,
              tokens JSONB NOT NULL DEFAULT '{}'::jsonb,
              description TEXT NOT NULL DEFAULT '',
              org_id TEXT NOT NULL DEFAULT 'dev-org',
              project_id TEXT NOT NULL DEFAULT 'dev-project',
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              PRIMARY KEY (org_id, project_id, id)
            )
            """
        )
        conn.commit()


def list_themes(scope: TenantScope) -> list[dict[str, Any]]:
    ensure_schema()
    with connect(scope) as conn:
        rows = conn.execute(
            """
            SELECT * FROM theme
             WHERE org_id=%s AND project_id=%s
             ORDER BY is_preset DESC, created_at
            """,
            scope.key,
        ).fetchall()
    return [_row(r) for r in rows]


def get_theme(scope: TenantScope, theme_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect(scope) as conn:
        row = conn.execute(
            """
            SELECT * FROM theme
             WHERE id=%s AND org_id=%s AND project_id=%s
            """,
            (theme_id, *scope.key),
        ).fetchone()
    return _row(row) if row else None


def create_theme(scope: TenantScope, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_schema()
    tid = payload.get("id") or f"theme-{uuid.uuid4().hex[:8]}"
    with connect(scope) as conn:
        result = conn.execute(
            """
            INSERT INTO theme (
                id, name, mode, is_preset, tokens, description, org_id, project_id
            ) VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
            ON CONFLICT (org_id, project_id, id) DO UPDATE SET
                name=EXCLUDED.name, mode=EXCLUDED.mode,
                tokens=EXCLUDED.tokens, description=EXCLUDED.description,
                updated_at=NOW()
            WHERE theme.org_id=EXCLUDED.org_id
              AND theme.project_id=EXCLUDED.project_id
            """,
            (
                tid,
                payload.get("name") or tid,
                payload.get("mode") or "light",
                bool(payload.get("isPreset") or payload.get("is_preset") or False),
                json.dumps(payload.get("tokens") or {}),
                payload.get("description") or "",
                *scope.key,
            ),
        )
        conn.commit()
    if result.rowcount == 0:
        raise PermissionError("theme belongs to another tenant")
    return get_theme(scope, tid)  # type: ignore[return-value]


def update_theme(
    scope: TenantScope, theme_id: str, patch: dict[str, Any]
) -> dict[str, Any] | None:
    cur = get_theme(scope, theme_id)
    if not cur:
        return None
    name = patch.get("name", cur["name"])
    mode = patch.get("mode", cur["mode"])
    tokens = patch.get("tokens", cur["tokens"])
    description = patch.get("description", cur.get("description", ""))
    with connect(scope) as conn:
        conn.execute(
            """
            UPDATE theme SET
                name=%s, mode=%s, tokens=%s::jsonb, description=%s, updated_at=NOW()
            WHERE id=%s AND org_id=%s AND project_id=%s
            """,
            (
                name,
                mode,
                json.dumps(tokens),
                description,
                theme_id,
                *scope.key,
            ),
        )
        conn.commit()
    return get_theme(scope, theme_id)


def delete_theme(scope: TenantScope, theme_id: str) -> bool:
    ensure_schema()
    with connect(scope) as conn:
        result = conn.execute(
            """
            DELETE FROM theme
             WHERE id=%s AND org_id=%s AND project_id=%s AND is_preset=FALSE
            """,
            (theme_id, *scope.key),
        )
        conn.commit()
        return result.rowcount > 0


def _row(r: dict[str, Any]) -> dict[str, Any]:
    tokens = r.get("tokens") or {}
    if isinstance(tokens, str):
        tokens = json.loads(tokens) if tokens else {}
    return {
        "id": r["id"],
        "name": r["name"],
        "mode": r.get("mode") or "light",
        "isPreset": bool(r.get("is_preset", False)),
        "tokens": tokens,
        "description": r.get("description") or "",
        "createdAt": str(r.get("created_at", "")),
        "updatedAt": str(r.get("updated_at", "")),
    }
