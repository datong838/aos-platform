"""Themes store — Phase 1 Workshop backend.

Stores theme presets (light/dark/high-contrast) with token maps.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.themes")

_DEFAULT_ORG = "dev-org"
_DEFAULT_PROJECT = "dev-project"


def ensure_schema() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS theme (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              mode TEXT NOT NULL DEFAULT 'light',
              is_preset BOOLEAN NOT NULL DEFAULT FALSE,
              tokens JSONB NOT NULL DEFAULT '{}'::jsonb,
              description TEXT NOT NULL DEFAULT '',
              org_id TEXT NOT NULL DEFAULT 'dev-org',
              project_id TEXT NOT NULL DEFAULT 'dev-project',
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.commit()


def list_themes() -> list[dict[str, Any]]:
    ensure_schema()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM theme
             WHERE org_id=%s AND project_id=%s
             ORDER BY is_preset DESC, created_at
            """,
            (_DEFAULT_ORG, _DEFAULT_PROJECT),
        ).fetchall()
    return [_row(r) for r in rows]


def get_theme(theme_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM theme
             WHERE id=%s AND org_id=%s AND project_id=%s
            """,
            (theme_id, _DEFAULT_ORG, _DEFAULT_PROJECT),
        ).fetchone()
    return _row(row) if row else None


def create_theme(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_schema()
    tid = payload.get("id") or f"theme-{uuid.uuid4().hex[:8]}"
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO theme (
                id, name, mode, is_preset, tokens, description, org_id, project_id
            ) VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
                name=EXCLUDED.name, mode=EXCLUDED.mode,
                tokens=EXCLUDED.tokens, description=EXCLUDED.description,
                updated_at=NOW()
            """,
            (
                tid,
                payload.get("name") or tid,
                payload.get("mode") or "light",
                bool(payload.get("isPreset") or payload.get("is_preset") or False),
                json.dumps(payload.get("tokens") or {}),
                payload.get("description") or "",
                _DEFAULT_ORG,
                _DEFAULT_PROJECT,
            ),
        )
        conn.commit()
    return get_theme(tid)  # type: ignore[return-value]


def update_theme(theme_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    cur = get_theme(theme_id)
    if not cur:
        return None
    name = patch.get("name", cur["name"])
    mode = patch.get("mode", cur["mode"])
    tokens = patch.get("tokens", cur["tokens"])
    description = patch.get("description", cur.get("description", ""))
    with connect() as conn:
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
                _DEFAULT_ORG,
                _DEFAULT_PROJECT,
            ),
        )
        conn.commit()
    return get_theme(theme_id)


def delete_theme(theme_id: str) -> bool:
    ensure_schema()
    with connect() as conn:
        result = conn.execute(
            """
            DELETE FROM theme
             WHERE id=%s AND org_id=%s AND project_id=%s AND is_preset=FALSE
            """,
            (theme_id, _DEFAULT_ORG, _DEFAULT_PROJECT),
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
