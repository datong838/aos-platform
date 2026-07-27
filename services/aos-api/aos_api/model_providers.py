"""Phase 2 · Model Providers — supplier registry + health metrics.

Stores provider connection info (base_url, masked api_key) and rolling
health metrics (p50 latency, availability %).
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.model_providers")

_DEFAULT_ORG = "dev-org"
_DEFAULT_PROJECT = "dev-project"


def ensure_schema() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS model_provider (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              base_url TEXT NOT NULL DEFAULT '',
              api_key_masked TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL DEFAULT 'normal',
              org_id TEXT NOT NULL DEFAULT 'dev-org',
              project_id TEXT NOT NULL DEFAULT 'dev-project',
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS provider_health (
              id TEXT PRIMARY KEY,
              provider_id TEXT NOT NULL,
              p50_latency_ms INTEGER NOT NULL DEFAULT 0,
              availability_pct NUMERIC(6,3) NOT NULL DEFAULT 100.000,
              checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              org_id TEXT NOT NULL DEFAULT 'dev-org',
              project_id TEXT NOT NULL DEFAULT 'dev-project'
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_provider_health_provider
            ON provider_health (provider_id, checked_at DESC)
            """
        )
        conn.commit()


def list_providers(*, status: str | None = None) -> list[dict[str, Any]]:
    ensure_schema()
    clauses = ["org_id=%s", "project_id=%s"]
    params: list[Any] = [_DEFAULT_ORG, _DEFAULT_PROJECT]
    if status:
        clauses.append("status=%s")
        params.append(status)
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM model_provider WHERE "
            + " AND ".join(clauses)
            + " ORDER BY created_at",
            tuple(params),
        ).fetchall()
        # attach latest health
        result = []
        for r in rows:
            d = _provider_row(r)
            health = conn.execute(
                """
                SELECT * FROM provider_health
                 WHERE provider_id=%s AND org_id=%s AND project_id=%s
                 ORDER BY checked_at DESC LIMIT 1
                """,
                (r["id"], _DEFAULT_ORG, _DEFAULT_PROJECT),
            ).fetchone()
            if health:
                d["p50LatencyMs"] = int(health.get("p50_latency_ms") or 0)
                d["availabilityPct"] = float(health.get("availability_pct") or 100.0)
            else:
                d["p50LatencyMs"] = 0
                d["availabilityPct"] = 100.0
            result.append(d)
    return result


def get_provider(provider_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM model_provider WHERE id=%s AND org_id=%s AND project_id=%s",
            (provider_id, _DEFAULT_ORG, _DEFAULT_PROJECT),
        ).fetchone()
        if not row:
            return None
        d = _provider_row(row)
        health = conn.execute(
            """
            SELECT * FROM provider_health
             WHERE provider_id=%s AND org_id=%s AND project_id=%s
             ORDER BY checked_at DESC LIMIT 1
            """,
            (provider_id, _DEFAULT_ORG, _DEFAULT_PROJECT),
        ).fetchone()
        if health:
            d["p50LatencyMs"] = int(health.get("p50_latency_ms") or 0)
            d["availabilityPct"] = float(health.get("availability_pct") or 100.0)
        else:
            d["p50LatencyMs"] = 0
            d["availabilityPct"] = 100.0
    return d


def create_provider(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_schema()
    pid = payload.get("id") or f"prov-{uuid.uuid4().hex[:8]}"
    raw_key = payload.get("apiKey") or payload.get("api_key") or ""
    masked = _mask_key(raw_key)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO model_provider (
                id, name, base_url, api_key_masked, status, org_id, project_id
            ) VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
                name=EXCLUDED.name, base_url=EXCLUDED.base_url,
                api_key_masked=EXCLUDED.api_key_masked, status=EXCLUDED.status,
                updated_at=NOW()
            """,
            (
                pid,
                payload["name"],
                payload.get("baseUrl") or payload.get("base_url") or "",
                masked,
                payload.get("status") or "normal",
                _DEFAULT_ORG,
                _DEFAULT_PROJECT,
            ),
        )
        conn.commit()
    return get_provider(pid)  # type: ignore[return-value]


def update_provider(provider_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    cur = get_provider(provider_id)
    if not cur:
        return None
    raw_key = patch.get("apiKey") or patch.get("api_key")
    masked = _mask_key(raw_key) if raw_key else cur.get("apiKeyMasked", "")
    with connect() as conn:
        conn.execute(
            """
            UPDATE model_provider SET
                name=%s, base_url=%s, api_key_masked=%s, status=%s, updated_at=NOW()
            WHERE id=%s AND org_id=%s AND project_id=%s
            """,
            (
                patch.get("name", cur["name"]),
                patch.get("baseUrl", cur.get("baseUrl", "")),
                masked,
                patch.get("status", cur["status"]),
                provider_id,
                _DEFAULT_ORG,
                _DEFAULT_PROJECT,
            ),
        )
        conn.commit()
    return get_provider(provider_id)


def delete_provider(provider_id: str) -> bool:
    ensure_schema()
    with connect() as conn:
        conn.execute(
            "DELETE FROM provider_health WHERE provider_id=%s AND org_id=%s AND project_id=%s",
            (provider_id, _DEFAULT_ORG, _DEFAULT_PROJECT),
        )
        result = conn.execute(
            "DELETE FROM model_provider WHERE id=%s AND org_id=%s AND project_id=%s",
            (provider_id, _DEFAULT_ORG, _DEFAULT_PROJECT),
        )
        conn.commit()
        return result.rowcount > 0


def get_provider_health(provider_id: str) -> dict[str, Any] | None:
    """Return the latest health snapshot for a provider."""
    ensure_schema()
    with connect() as conn:
        prov = conn.execute(
            "SELECT * FROM model_provider WHERE id=%s AND org_id=%s AND project_id=%s",
            (provider_id, _DEFAULT_ORG, _DEFAULT_PROJECT),
        ).fetchone()
        if not prov:
            return None
        health = conn.execute(
            """
            SELECT * FROM provider_health
             WHERE provider_id=%s AND org_id=%s AND project_id=%s
             ORDER BY checked_at DESC LIMIT 1
            """,
            (provider_id, _DEFAULT_ORG, _DEFAULT_PROJECT),
        ).fetchone()
    return {
        "providerId": provider_id,
        "name": prov["name"],
        "status": prov.get("status") or "normal",
        "p50LatencyMs": int(health.get("p50_latency_ms") or 0) if health else 0,
        "availabilityPct": float(health.get("availability_pct") or 100.0) if health else 100.0,
        "checkedAt": str(health.get("checked_at", "")) if health else "",
    }


def upsert_provider_health(
    provider_id: str, p50_latency_ms: int, availability_pct: float
) -> dict[str, Any]:
    ensure_schema()
    hid = f"ph-{uuid.uuid4().hex[:8]}"
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO provider_health (
                id, provider_id, p50_latency_ms, availability_pct, org_id, project_id
            ) VALUES (%s,%s,%s,%s,%s,%s)
            """,
            (hid, provider_id, int(p50_latency_ms), float(availability_pct), _DEFAULT_ORG, _DEFAULT_PROJECT),
        )
        conn.commit()
    return {"id": hid, "providerId": provider_id, "p50LatencyMs": int(p50_latency_ms),
            "availabilityPct": float(availability_pct)}


def _mask_key(raw: str) -> str:
    if not raw:
        return ""
    if len(raw) <= 8:
        return "***"
    return raw[:4] + "***" + raw[-4:]


def _provider_row(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": r["id"],
        "name": r["name"],
        "baseUrl": r.get("base_url") or "",
        "apiKeyMasked": r.get("api_key_masked") or "",
        "status": r.get("status") or "normal",
        "createdAt": str(r.get("created_at", "")),
        "updatedAt": str(r.get("updated_at", "")),
    }
