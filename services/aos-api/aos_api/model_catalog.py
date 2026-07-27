"""Phase 2 · Model Catalog — discoverable model registry.

Stores model discovery metadata (provider, capabilities, pricing, status).
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.model_catalog")

_DEFAULT_ORG = "dev-org"
_DEFAULT_PROJECT = "dev-project"


def ensure_schema() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS model_catalog (
              id TEXT PRIMARY KEY,
              provider TEXT NOT NULL,
              model TEXT NOT NULL,
              display_name TEXT NOT NULL DEFAULT '',
              capabilities JSONB NOT NULL DEFAULT '[]'::jsonb,
              context_window INTEGER NOT NULL DEFAULT 4096,
              input_price NUMERIC(12,6) NOT NULL DEFAULT 0,
              output_price NUMERIC(12,6) NOT NULL DEFAULT 0,
              status TEXT NOT NULL DEFAULT 'ga',
              description TEXT NOT NULL DEFAULT '',
              org_id TEXT NOT NULL DEFAULT 'dev-org',
              project_id TEXT NOT NULL DEFAULT 'dev-project',
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.commit()


def list_catalog(
    *,
    provider: str | None = None,
    status: str | None = None,
    capability: str | None = None,
) -> list[dict[str, Any]]:
    ensure_schema()
    clauses = ["org_id=%s", "project_id=%s"]
    params: list[Any] = [_DEFAULT_ORG, _DEFAULT_PROJECT]
    if provider:
        clauses.append("provider=%s")
        params.append(provider)
    if status:
        clauses.append("status=%s")
        params.append(status)
    if capability:
        clauses.append("capabilities @> %s::jsonb")
        params.append(json.dumps([capability]))
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM model_catalog WHERE " + " AND ".join(clauses) + " ORDER BY created_at",
            tuple(params),
        ).fetchall()
    return [_row(r) for r in rows]


def get_catalog(model_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM model_catalog WHERE id=%s AND org_id=%s AND project_id=%s",
            (model_id, _DEFAULT_ORG, _DEFAULT_PROJECT),
        ).fetchone()
    return _row(row) if row else None


def create_catalog(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_schema()
    mid = payload.get("id") or f"mc-{uuid.uuid4().hex[:8]}"
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO model_catalog (
                id, provider, model, display_name, capabilities,
                context_window, input_price, output_price, status, description,
                org_id, project_id
            ) VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
                provider=EXCLUDED.provider, model=EXCLUDED.model,
                display_name=EXCLUDED.display_name, capabilities=EXCLUDED.capabilities,
                context_window=EXCLUDED.context_window, input_price=EXCLUDED.input_price,
                output_price=EXCLUDED.output_price, status=EXCLUDED.status,
                description=EXCLUDED.description, updated_at=NOW()
            """,
            (
                mid,
                payload["provider"],
                payload["model"],
                payload.get("displayName") or payload.get("display_name") or payload["model"],
                json.dumps(payload.get("capabilities") or []),
                int(payload.get("contextWindow") or payload.get("context_window") or 4096),
                float(payload.get("inputPrice") or payload.get("input_price") or 0),
                float(payload.get("outputPrice") or payload.get("output_price") or 0),
                payload.get("status") or "ga",
                payload.get("description") or "",
                _DEFAULT_ORG,
                _DEFAULT_PROJECT,
            ),
        )
        conn.commit()
    return get_catalog(mid)  # type: ignore[return-value]


def update_catalog(model_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    cur = get_catalog(model_id)
    if not cur:
        return None
    with connect() as conn:
        conn.execute(
            """
            UPDATE model_catalog SET
                provider=%s, model=%s, display_name=%s, capabilities=%s::jsonb,
                context_window=%s, input_price=%s, output_price=%s, status=%s,
                description=%s, updated_at=NOW()
            WHERE id=%s AND org_id=%s AND project_id=%s
            """,
            (
                patch.get("provider", cur["provider"]),
                patch.get("model", cur["model"]),
                patch.get("displayName", cur.get("displayName", "")),
                json.dumps(patch.get("capabilities", cur["capabilities"])),
                int(patch.get("contextWindow", cur["contextWindow"])),
                float(patch.get("inputPrice", cur["inputPrice"])),
                float(patch.get("outputPrice", cur["outputPrice"])),
                patch.get("status", cur["status"]),
                patch.get("description", cur.get("description", "")),
                model_id,
                _DEFAULT_ORG,
                _DEFAULT_PROJECT,
            ),
        )
        conn.commit()
    return get_catalog(model_id)


def delete_catalog(model_id: str) -> bool:
    ensure_schema()
    with connect() as conn:
        result = conn.execute(
            "DELETE FROM model_catalog WHERE id=%s AND org_id=%s AND project_id=%s",
            (model_id, _DEFAULT_ORG, _DEFAULT_PROJECT),
        )
        conn.commit()
        return result.rowcount > 0


def _row(r: dict[str, Any]) -> dict[str, Any]:
    caps = r.get("capabilities") or []
    if isinstance(caps, str):
        caps = json.loads(caps) if caps else []
    return {
        "id": r["id"],
        "provider": r["provider"],
        "model": r["model"],
        "displayName": r.get("display_name") or r["model"],
        "capabilities": caps,
        "contextWindow": int(r.get("context_window") or 4096),
        "inputPrice": float(r.get("input_price") or 0),
        "outputPrice": float(r.get("output_price") or 0),
        "status": r.get("status") or "ga",
        "description": r.get("description") or "",
        "createdAt": str(r.get("created_at", "")),
        "updatedAt": str(r.get("updated_at", "")),
    }
