"""Module Meta Store on PostgreSQL (T08) — replaces in-memory mock for modules.

TWA.5: rows scoped by org_id + project_id (configured instances are per-workspace).
"""
from __future__ import annotations

import json
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.module_store")

_DEFAULT_ORG = "dev-org"
_DEFAULT_PROJECT = "dev-project"

_SEED = [
    {
        "id": "mod-ops-inbox",
        "name": "运营台 Inbox",
        "status": "published",
        "description": "Demo-aligned Module for Workshop Inbox",
        "objectType": "WorkOrder",
        "markings": ["public"],
        "entryPath": "/workshop/inbox",
        "widgets": ["table", "filters", "selection"],
        "buddyBound": True,
    },
    {
        "id": "mod-canvas-draft",
        "name": "画布草稿",
        "status": "draft",
        "description": "Canvas editor placeholder",
        "objectType": "WorkOrder",
        "markings": ["restricted"],
        "entryPath": "/workshop/canvas",
        "widgets": ["canvas"],
        "buddyBound": False,
    },
    {
        "id": "mod-buddy-assist",
        "name": "Buddy 助手",
        "status": "published",
        "description": "AIP Assist Module",
        "objectType": "WorkOrder",
        "markings": ["public"],
        "entryPath": "/workshop/buddy",
        "widgets": ["chat"],
        "buddyBound": True,
    },
]


def ensure_module_schema() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta_module (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'draft',
              description TEXT NOT NULL DEFAULT '',
              object_type TEXT NOT NULL DEFAULT 'WorkOrder',
              markings JSONB NOT NULL DEFAULT '["public"]'::jsonb,
              entry_path TEXT NOT NULL DEFAULT '/workshop/inbox',
              widgets JSONB NOT NULL DEFAULT '["table"]'::jsonb,
              buddy_bound BOOLEAN NOT NULL DEFAULT TRUE,
              org_id TEXT NOT NULL DEFAULT 'dev-org',
              project_id TEXT NOT NULL DEFAULT 'dev-project',
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        # migrate pre-TWA.5 tables
        conn.execute(
            """
            ALTER TABLE meta_module
              ADD COLUMN IF NOT EXISTS org_id TEXT NOT NULL DEFAULT 'dev-org'
            """
        )
        conn.execute(
            """
            ALTER TABLE meta_module
              ADD COLUMN IF NOT EXISTS project_id TEXT NOT NULL DEFAULT 'dev-project'
            """
        )
        conn.execute(
            """
            UPDATE meta_module
               SET org_id = COALESCE(NULLIF(org_id, ''), 'dev-org'),
                   project_id = COALESCE(NULLIF(project_id, ''), 'dev-project')
            """
        )
        conn.commit()


def _row_to_mod(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": r["id"],
        "name": r["name"],
        "status": r["status"],
        "description": r["description"] or "",
        "objectType": r["object_type"],
        "markings": r["markings"] if isinstance(r["markings"], list) else list(r["markings"] or []),
        "entryPath": r["entry_path"],
        "widgets": r["widgets"] if isinstance(r["widgets"], list) else list(r["widgets"] or []),
        "buddyBound": bool(r["buddy_bound"]),
        "orgId": r.get("org_id") or _DEFAULT_ORG,
        "projectId": r.get("project_id") or _DEFAULT_PROJECT,
    }


def seed_modules_if_empty() -> None:
    ensure_module_schema()
    with connect() as conn:
        for s in _SEED:
            conn.execute(
                """
                INSERT INTO meta_module (
                  id, name, status, description, object_type, markings,
                  entry_path, widgets, buddy_bound, org_id, project_id
                ) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,%s,%s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    s["id"],
                    s["name"],
                    s["status"],
                    s["description"],
                    s["objectType"],
                    json.dumps(s["markings"]),
                    s["entryPath"],
                    json.dumps(s["widgets"]),
                    s["buddyBound"],
                    _DEFAULT_ORG,
                    _DEFAULT_PROJECT,
                ),
            )
        conn.commit()
    log.info(
        "module_store_seed_ensured org=%s project=%s",
        _DEFAULT_ORG,
        _DEFAULT_PROJECT,
    )


def list_modules(org_id: str, project_id: str) -> list[dict[str, Any]]:
    ensure_module_schema()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM meta_module
             WHERE org_id=%s AND project_id=%s
             ORDER BY id
            """,
            (org_id, project_id),
        ).fetchall()
    log.info(
        "module_list org=%s project=%s count=%s",
        org_id,
        project_id,
        len(rows),
    )
    return [_row_to_mod(r) for r in rows]


def get_module(
    module_id: str, org_id: str, project_id: str
) -> dict[str, Any] | None:
    ensure_module_schema()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM meta_module
             WHERE id=%s AND org_id=%s AND project_id=%s
            """,
            (module_id, org_id, project_id),
        ).fetchone()
    if not row:
        log.warning(
            "module_miss id=%s org=%s project=%s",
            module_id,
            org_id,
            project_id,
        )
        return None
    return _row_to_mod(row)


def create_module(
    payload: dict[str, Any], *, org_id: str, project_id: str
) -> dict[str, Any]:
    ensure_module_schema()
    import uuid

    mid = payload.get("id") or f"mod-{uuid.uuid4().hex[:8]}"
    item = {
        "id": mid,
        "name": payload.get("name") or mid,
        "status": payload.get("status") or "draft",
        "description": payload.get("description") or "",
        "objectType": payload.get("objectType") or "WorkOrder",
        "markings": payload.get("markings") or ["public"],
        "entryPath": payload.get("entryPath") or "/workshop/inbox",
        "widgets": payload.get("widgets") or ["table", "filters"],
        "buddyBound": bool(payload.get("buddyBound", True)),
        "orgId": org_id,
        "projectId": project_id,
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO meta_module (
              id, name, status, description, object_type, markings,
              entry_path, widgets, buddy_bound, org_id, project_id
            ) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,%s,%s)
            """,
            (
                item["id"],
                item["name"],
                item["status"],
                item["description"],
                item["objectType"],
                json.dumps(item["markings"]),
                item["entryPath"],
                json.dumps(item["widgets"]),
                item["buddyBound"],
                org_id,
                project_id,
            ),
        )
        conn.commit()
    log.info(
        "module_create id=%s org=%s project=%s",
        mid,
        org_id,
        project_id,
    )
    return item


def update_module(
    module_id: str,
    patch: dict[str, Any],
    *,
    org_id: str,
    project_id: str,
) -> dict[str, Any] | None:
    cur = get_module(module_id, org_id, project_id)
    if not cur:
        return None
    mapping = {
        "name": "name",
        "description": "description",
        "objectType": "objectType",
        "markings": "markings",
        "entryPath": "entryPath",
        "widgets": "widgets",
        "buddyBound": "buddyBound",
        "status": "status",
    }
    for k, v in patch.items():
        if k in mapping and v is not None:
            cur[mapping[k]] = v
    with connect() as conn:
        conn.execute(
            """
            UPDATE meta_module SET
              name=%s, status=%s, description=%s, object_type=%s,
              markings=%s::jsonb, entry_path=%s, widgets=%s::jsonb, buddy_bound=%s
            WHERE id=%s AND org_id=%s AND project_id=%s
            """,
            (
                cur["name"],
                cur["status"],
                cur["description"],
                cur["objectType"],
                json.dumps(cur["markings"]),
                cur["entryPath"],
                json.dumps(cur["widgets"]),
                cur["buddyBound"],
                module_id,
                org_id,
                project_id,
            ),
        )
        conn.commit()
    return get_module(module_id, org_id, project_id)


def publish_module(
    module_id: str, *, org_id: str, project_id: str
) -> dict[str, Any] | None:
    mod = update_module(
        module_id, {"status": "published"}, org_id=org_id, project_id=project_id
    )
    if not mod:
        return None
    return {
        **mod,
        "publish": {
            "adapter": "apollo-lite",
            "channel": "dev",
            "status": "ACCEPTED",
        },
    }


def module_runtime(
    module_id: str, *, org_id: str, project_id: str
) -> dict[str, Any] | None:
    mod = get_module(module_id, org_id, project_id)
    if not mod:
        return None
    return {
        "moduleId": module_id,
        "layout": {"widgets": mod.get("widgets") or ["table", "filters", "selection"]},
        "variables": {"selectionLimit": 10},
        "events": [{"id": "refresh", "type": "query"}],
        "objectType": mod["objectType"],
        "entryPath": mod.get("entryPath") or "/workshop/inbox",
        "buddyBound": bool(mod.get("buddyBound", False)),
        "orgId": org_id,
        "projectId": project_id,
        "store": "postgres",
    }
