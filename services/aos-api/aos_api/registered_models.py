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

log = get_logger("aos-api.registered_models")

_DEFAULT_ORG = "dev-org"
_DEFAULT_PROJECT = "dev-project"


def ensure_schema() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS registered_models (
              id TEXT PRIMARY KEY,
              model_id TEXT NOT NULL,
              alias TEXT NOT NULL DEFAULT '',
              quota JSONB NOT NULL DEFAULT '{}'::jsonb,
              status TEXT NOT NULL DEFAULT 'enabled',
              org_id TEXT NOT NULL DEFAULT 'dev-org',
              project_id TEXT NOT NULL DEFAULT 'dev-project',
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_registered_models_org
            ON registered_models (org_id, project_id)
            """
        )
        conn.commit()


def list_registered(
    *,
    status: str | None = None,
    model_id: str | None = None,
) -> list[dict[str, Any]]:
    ensure_schema()
    clauses = ["org_id=%s", "project_id=%s"]
    params: list[Any] = [_DEFAULT_ORG, _DEFAULT_PROJECT]
    if status:
        clauses.append("status=%s")
        params.append(status)
    if model_id:
        clauses.append("model_id=%s")
        params.append(model_id)
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM registered_models WHERE "
            + " AND ".join(clauses)
            + " ORDER BY created_at",
            tuple(params),
        ).fetchall()
    return [_row(r) for r in rows]


def get_registered(reg_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM registered_models WHERE id=%s AND org_id=%s AND project_id=%s",
            (reg_id, _DEFAULT_ORG, _DEFAULT_PROJECT),
        ).fetchone()
    return _row(row) if row else None


def register_model(payload: dict[str, Any]) -> dict[str, Any]:
    """Register a catalog model into the org. Idempotent on model_id."""
    ensure_schema()
    rid = payload.get("id") or f"rm-{uuid.uuid4().hex[:8]}"
    quota = payload.get("quota") or {}
    if not isinstance(quota, dict):
        quota = {}
    # default quota
    quota.setdefault("rpm", 60)
    quota.setdefault("tpm", 60000)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO registered_models (
                id, model_id, alias, quota, status, org_id, project_id
            ) VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
                model_id=EXCLUDED.model_id, alias=EXCLUDED.alias,
                quota=EXCLUDED.quota, status=EXCLUDED.status, updated_at=NOW()
            """,
            (
                rid,
                payload["modelId"],
                payload.get("alias") or "",
                json.dumps(quota),
                payload.get("status") or "enabled",
                _DEFAULT_ORG,
                _DEFAULT_PROJECT,
            ),
        )
        conn.commit()
    return get_registered(rid)  # type: ignore[return-value]


def update_registered(reg_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    cur = get_registered(reg_id)
    if not cur:
        return None
    quota = patch.get("quota", cur["quota"])
    with connect() as conn:
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
                _DEFAULT_ORG,
                _DEFAULT_PROJECT,
            ),
        )
        conn.commit()
    return get_registered(reg_id)


def unregister_model(reg_id: str) -> bool:
    ensure_schema()
    with connect() as conn:
        result = conn.execute(
            "DELETE FROM registered_models WHERE id=%s AND org_id=%s AND project_id=%s",
            (reg_id, _DEFAULT_ORG, _DEFAULT_PROJECT),
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
