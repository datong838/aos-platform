"""Phase 2 · Registered Models — org-registered models with quota.

Links a catalog model to an org-specific registration with quota (rpm/tpm),
status (enabled/disabled) and alias.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.tenant_scope import TenantScope

log = get_logger("aos-api.registered_models")


def ensure_schema() -> None:
    """Compatibility hook; schema ownership moved to Alembic in TI-5 B1."""


def list_registered(
    scope: TenantScope,
    *,
    status: str | None = None,
    model_id: str | None = None,
) -> list[dict[str, Any]]:
    ensure_schema()
    clauses = ["org_id=%s", "project_id=%s"]
    params: list[Any] = list(scope.key)
    if status:
        clauses.append("status=%s")
        params.append(status)
    if model_id:
        clauses.append("model_id=%s")
        params.append(model_id)
    with connect(scope) as conn:
        rows = conn.execute(
            "SELECT * FROM registered_models WHERE "
            + " AND ".join(clauses)
            + " ORDER BY created_at",
            tuple(params),
        ).fetchall()
    return [_row(r) for r in rows]


def get_registered(scope: TenantScope, reg_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect(scope) as conn:
        row = conn.execute(
            "SELECT * FROM registered_models WHERE id=%s AND org_id=%s AND project_id=%s",
            (reg_id, *scope.key),
        ).fetchone()
    return _row(row) if row else None


def register_model(scope: TenantScope, payload: dict[str, Any]) -> dict[str, Any]:
    """Register a catalog model into the org. Idempotent on model_id."""
    ensure_schema()
    rid = payload.get("id") or f"rm-{uuid.uuid4().hex[:8]}"
    quota = payload.get("quota") or {}
    if not isinstance(quota, dict):
        quota = {}
    # default quota
    quota.setdefault("rpm", 60)
    quota.setdefault("tpm", 60000)
    with connect(scope) as conn:
        conn.execute(
            """
            INSERT INTO registered_models (
                id, model_id, alias, quota, status, org_id, project_id
            ) VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s)
            ON CONFLICT (org_id,project_id,id) DO UPDATE SET
                model_id=EXCLUDED.model_id, alias=EXCLUDED.alias,
                quota=EXCLUDED.quota, status=EXCLUDED.status, updated_at=NOW()
            """,
            (
                rid,
                payload["modelId"],
                payload.get("alias") or "",
                json.dumps(quota),
                payload.get("status") or "enabled",
                *scope.key,
            ),
        )
        conn.commit()
    return get_registered(scope, rid)  # type: ignore[return-value]


def update_registered(
    scope: TenantScope, reg_id: str, patch: dict[str, Any]
) -> dict[str, Any] | None:
    cur = get_registered(scope, reg_id)
    if not cur:
        return None
    quota = patch.get("quota", cur["quota"])
    with connect(scope) as conn:
        conn.execute(
            """
            UPDATE registered_models SET
                alias=%s, quota=%s::jsonb, status=%s, updated_at=NOW()
            WHERE id=%s AND org_id=%s AND project_id=%s
            """,
            (
                patch.get("alias", cur.get("alias", "")),
                json.dumps(quota),
                patch.get("status", cur["status"]),
                reg_id,
                *scope.key,
            ),
        )
        conn.commit()
    return get_registered(scope, reg_id)


def unregister_model(scope: TenantScope, reg_id: str) -> bool:
    ensure_schema()
    with connect(scope) as conn:
        result = conn.execute(
            "DELETE FROM registered_models WHERE id=%s AND org_id=%s AND project_id=%s",
            (reg_id, *scope.key),
        )
        conn.commit()
        return result.rowcount > 0


def _row(r: dict[str, Any]) -> dict[str, Any]:
    quota = r.get("quota") or {}
    if isinstance(quota, str):
        quota = json.loads(quota) if quota else {}
    return {
        "id": r["id"],
        "modelId": r["model_id"],
        "alias": r.get("alias") or "",
        "quota": quota,
        "status": r.get("status") or "enabled",
        "createdAt": str(r.get("created_at", "")),
        "updatedAt": str(r.get("updated_at", "")),
    }
