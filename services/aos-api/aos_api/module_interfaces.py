"""Module interface store — Phase 1 Workshop backend.

Stores module API/interface definitions (entry params, expose config).
"""
from __future__ import annotations

import json
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.module_identity import resolve_module_pk
from aos_api.tenant_scope import TenantScope

log = get_logger("aos-api.module_interfaces")

_VALID_DIRECTIONS = frozenset({"input", "output"})


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


def normalize_param(raw: Any) -> dict[str, Any] | None:
    """Normalize a single param dict; accept name/key and direction."""
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or raw.get("key") or "").strip()
    if not name:
        return None
    direction = str(raw.get("direction") or "input").strip().lower()
    if direction not in _VALID_DIRECTIONS:
        direction = "input"
    typ = str(raw.get("type") or "string")
    item: dict[str, Any] = {
        "name": name,
        "key": name,
        "type": typ,
        "direction": direction,
    }
    if "required" in raw:
        item["required"] = bool(raw["required"])
    return item


def normalize_entry_params(
    entry_params: Any = None,
    output_params: Any = None,
) -> list[dict[str, Any]]:
    """Merge entryParams + optional outputParams into a normalized list."""
    out: list[dict[str, Any]] = []
    for raw in entry_params or []:
        item = normalize_param(raw)
        if item:
            out.append(item)
    for raw in output_params or []:
        item = normalize_param(raw)
        if not item:
            continue
        item["direction"] = "output"
        out.append(item)
    return out


def get_interface(scope: TenantScope, module_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        row = (
            conn.execute(
                "SELECT * FROM module_interface "
                "WHERE module_pk=%s AND org_id=%s AND project_id=%s",
                (module_pk, *scope.key),
            ).fetchone()
            if module_pk is not None
            else None
        )
    return _row(row) if row else None


def put_interface(
    scope: TenantScope, module_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    ensure_schema()
    name = payload.get("name") or ""
    description = payload.get("description") or ""
    entry_params = normalize_entry_params(
        payload.get("entryParams") or payload.get("entry_params") or [],
        payload.get("outputParams") or payload.get("output_params") or [],
    )
    expose = payload.get("expose") or {}
    version = payload.get("version") or "1.0.0"
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        if module_pk is None:
            raise PermissionError("module interface parent is unavailable in tenant scope")
        result = conn.execute(
            """
            INSERT INTO module_interface (
                module_id, name, description, entry_params, expose,
                version, org_id, project_id, module_pk
            ) VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s)
            ON CONFLICT (org_id, project_id, module_pk) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                entry_params = EXCLUDED.entry_params,
                expose = EXCLUDED.expose,
                version = EXCLUDED.version,
                module_pk = COALESCE(module_interface.module_pk, EXCLUDED.module_pk),
                updated_at = NOW()
            WHERE module_interface.org_id=EXCLUDED.org_id
              AND module_interface.project_id=EXCLUDED.project_id
            """,
            (
                module_id,
                name,
                description,
                json.dumps(entry_params),
                json.dumps(expose),
                version,
                *scope.key,
                module_pk,
            ),
        )
        conn.commit()
    if result.rowcount == 0:
        raise PermissionError("module interface belongs to another tenant")
    return get_interface(scope, module_id)  # type: ignore[return-value]


def _row(r: dict[str, Any]) -> dict[str, Any]:
    ep = r.get("entry_params") or []
    if isinstance(ep, str):
        ep = json.loads(ep) if ep else []
    ex = r.get("expose") or {}
    if isinstance(ex, str):
        ex = json.loads(ex) if ex else {}
    normalized = normalize_entry_params(ep)
    return {
        "moduleId": r["module_id"],
        "name": r.get("name") or "",
        "description": r.get("description") or "",
        "entryParams": normalized,
        "expose": ex,
        "version": r.get("version") or "1.0.0",
        "updatedAt": str(r.get("updated_at", "")),
    }
