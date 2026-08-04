"""Module deployments store — Phase 1 Workshop backend.

Stores deployment history (publish to dev/staging/prod) and supports rollback.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.module_identity import resolve_module_pk
from aos_api.tenant_scope import TenantScope

log = get_logger("aos-api.module_deployments")

def ensure_schema() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS module_deployment (
              id TEXT PRIMARY KEY,
              module_id TEXT NOT NULL,
              environment TEXT NOT NULL DEFAULT 'dev',
              version TEXT NOT NULL DEFAULT '1.0.0',
              status TEXT NOT NULL DEFAULT 'success',
              config_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
              deployed_by TEXT NOT NULL DEFAULT 'user:dev',
              rolled_back_from TEXT,
              org_id TEXT NOT NULL DEFAULT 'dev-org',
              project_id TEXT NOT NULL DEFAULT 'dev-project',
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_md_module
            ON module_deployment(module_id, org_id, project_id)
            """
        )
        conn.commit()


def list_deployments(scope: TenantScope, module_id: str) -> list[dict[str, Any]]:
    ensure_schema()
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        rows = (
            conn.execute(
                "SELECT * FROM module_deployment "
                "WHERE module_pk=%s AND org_id=%s AND project_id=%s "
                "ORDER BY created_at DESC",
                (module_pk, *scope.key),
            ).fetchall()
            if module_pk is not None
            else []
        )
    return [_row(r) for r in rows]


def deploy(
    scope: TenantScope,
    module_id: str,
    environment: str,
    *,
    version: str = "1.0.0",
    config_snapshot: dict | None = None,
    deployed_by: str = "user:dev",
) -> dict[str, Any]:
    ensure_schema()
    did = f"dep-{module_id}-{environment}-{uuid.uuid4().hex[:6]}"
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        conn.execute(
            """
            INSERT INTO module_deployment (
                id, module_id, environment, version, status,
                config_snapshot, deployed_by, org_id, project_id, module_pk
            ) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
            """,
            (
                did,
                module_id,
                environment,
                version,
                "success",
                json.dumps(config_snapshot or {}),
                deployed_by,
                *scope.key,
                module_pk,
            ),
        )
        conn.commit()
    return get_deployment(scope, module_id, did)  # type: ignore[return-value]


def get_deployment(
    scope: TenantScope, module_id: str, deployment_id: str
) -> dict[str, Any] | None:
    ensure_schema()
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        row = (
            conn.execute(
                "SELECT * FROM module_deployment "
                "WHERE id=%s AND module_pk=%s AND org_id=%s AND project_id=%s",
                (deployment_id, module_pk, *scope.key),
            ).fetchone()
            if module_pk is not None
            else None
        )
    return _row(row) if row else None


def rollback(
    scope: TenantScope,
    module_id: str,
    target_deployment_id: str,
    *,
    deployed_by: str = "user:dev",
) -> dict[str, Any] | None:
    """Rollback to a previous deployment by creating a new deployment record."""
    target = get_deployment(scope, module_id, target_deployment_id)
    if not target:
        return None
    ensure_schema()
    new_id = f"dep-{module_id}-{target['environment']}-rb-{uuid.uuid4().hex[:6]}"
    with connect(scope) as conn:
        module_pk = resolve_module_pk(conn, scope, module_id)
        conn.execute(
            """
            INSERT INTO module_deployment (
                id, module_id, environment, version, status,
                config_snapshot, deployed_by, rolled_back_from, org_id, project_id,
                module_pk
            ) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)
            """,
            (
                new_id,
                module_id,
                target["environment"],
                target["version"],
                "rollback",
                json.dumps(target.get("configSnapshot") or {}),
                deployed_by,
                target_deployment_id,
                *scope.key,
                module_pk,
            ),
        )
        conn.commit()
    return get_deployment(scope, module_id, new_id)


def _row(r: dict[str, Any]) -> dict[str, Any]:
    snap = r.get("config_snapshot") or {}
    if isinstance(snap, str):
        snap = json.loads(snap) if snap else {}
    return {
        "id": r["id"],
        "moduleId": r["module_id"],
        "environment": r.get("environment") or "dev",
        "version": r.get("version") or "1.0.0",
        "status": r.get("status") or "success",
        "configSnapshot": snap,
        "deployedBy": r.get("deployed_by") or "user:dev",
        "rolledBackFrom": r.get("rolled_back_from"),
        "createdAt": str(r.get("created_at", "")),
    }
