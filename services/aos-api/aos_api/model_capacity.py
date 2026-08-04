"""Phase 2 · Model Capacity — rate limits + daily usage.

capacity_limits: per-org / per-project / per-user rate limits (rpm/tpm).
capacity_usage: daily aggregated metrics (requests, tokens, cost, peak_rpm).
"""

from __future__ import annotations

import uuid
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.tenant_scope import TenantScope

log = get_logger("aos-api.model_capacity")

# Scope constants
SCOPE_PROJECT = "project"
SCOPE_USER = "user"


def ensure_schema() -> None:
    """Compatibility hook; schema ownership moved to Alembic in TI-5 B1."""


# ── Limits ──


def list_limits(
    tenant: TenantScope, scope: str, *, scope_key: str | None = None
) -> list[dict[str, Any]]:
    ensure_schema()
    clauses = ["org_id=%s", "project_id=%s", "scope=%s"]
    params: list[Any] = [*tenant.key, scope]
    if scope_key:
        clauses.append("scope_key=%s")
        params.append(scope_key)
    with connect(tenant) as conn:
        rows = conn.execute(
            "SELECT * FROM capacity_limits WHERE "
            + " AND ".join(clauses)
            + " ORDER BY created_at",
            tuple(params),
        ).fetchall()
    return [_limit_row(r) for r in rows]


def get_limit(tenant: TenantScope, limit_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect(tenant) as conn:
        row = conn.execute(
            "SELECT * FROM capacity_limits WHERE id=%s AND org_id=%s AND project_id=%s",
            (limit_id, *tenant.key),
        ).fetchone()
    return _limit_row(row) if row else None


def get_or_default_limit(
    tenant: TenantScope, scope: str, scope_key: str
) -> dict[str, Any]:
    """Get limit by scope+key, falling back to defaults if not set."""
    items = list_limits(tenant, scope, scope_key=scope_key)
    if items:
        return items[0]
    return {
        "id": "",
        "scope": scope,
        "scopeKey": scope_key,
        "rpmLimit": 60,
        "tpmLimit": 60000,
    }


def upsert_limit(
    tenant: TenantScope, scope: str, scope_key: str, payload: dict[str, Any]
) -> dict[str, Any]:
    ensure_schema()
    with connect(tenant) as conn:
        existing = conn.execute(
            """
            SELECT id FROM capacity_limits
             WHERE org_id=%s AND project_id=%s AND scope=%s AND scope_key=%s
            """,
            (*tenant.key, scope, scope_key),
        ).fetchone()
        lid = existing["id"] if existing else f"cl-{uuid.uuid4().hex[:8]}"
        conn.execute(
            """
            INSERT INTO capacity_limits (
                id, scope, scope_key, rpm_limit, tpm_limit, org_id, project_id
            ) VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (org_id,project_id,id) DO UPDATE SET
                scope=EXCLUDED.scope, scope_key=EXCLUDED.scope_key,
                rpm_limit=EXCLUDED.rpm_limit, tpm_limit=EXCLUDED.tpm_limit,
                updated_at=NOW()
            """,
            (
                lid,
                scope,
                scope_key,
                int(payload.get("rpmLimit") or 60),
                int(payload.get("tpmLimit") or 60000),
                *tenant.key,
            ),
        )
        conn.commit()
    return get_limit(tenant, lid)  # type: ignore[return-value]


# ── Usage ──


def list_usage(
    tenant: TenantScope,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    ensure_schema()
    clauses = ["org_id=%s", "project_id=%s"]
    params: list[Any] = list(tenant.key)
    if start_date:
        clauses.append("day>=%s")
        params.append(start_date)
    if end_date:
        clauses.append("day<=%s")
        params.append(end_date)
    with connect(tenant) as conn:
        rows = conn.execute(
            "SELECT * FROM capacity_usage WHERE "
            + " AND ".join(clauses)
            + " ORDER BY day DESC LIMIT %s",
            tuple(params + [limit]),
        ).fetchall()
    return [_usage_row(r) for r in rows]


def upsert_usage(tenant: TenantScope, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_schema()
    uid = payload.get("id") or f"cu-{uuid.uuid4().hex[:8]}"
    with connect(tenant) as conn:
        existing = conn.execute(
            """
            SELECT id FROM capacity_usage
             WHERE org_id=%s AND project_id=%s AND day=%s
            """,
            (*tenant.key, payload["day"]),
        ).fetchone()
        uid = existing["id"] if existing else uid
        conn.execute(
            """
            INSERT INTO capacity_usage (
                id, day, total_requests, total_tokens, cost, peak_rpm, org_id, project_id
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (org_id,project_id,id) DO UPDATE SET
                day=EXCLUDED.day, total_requests=EXCLUDED.total_requests,
                total_tokens=EXCLUDED.total_tokens, cost=EXCLUDED.cost,
                peak_rpm=EXCLUDED.peak_rpm
            """,
            (
                uid,
                payload["day"],
                int(payload.get("totalRequests") or 0),
                int(payload.get("totalTokens") or 0),
                float(payload.get("cost") or 0),
                int(payload.get("peakRpm") or 0),
                *tenant.key,
            ),
        )
        conn.commit()
    return get_usage(tenant, uid)  # type: ignore[return-value]


def get_usage(tenant: TenantScope, usage_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect(tenant) as conn:
        row = conn.execute(
            "SELECT * FROM capacity_usage WHERE id=%s AND org_id=%s AND project_id=%s",
            (usage_id, *tenant.key),
        ).fetchone()
    return _usage_row(row) if row else None


def _limit_row(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": r["id"],
        "scope": r["scope"],
        "scopeKey": r.get("scope_key") or "",
        "rpmLimit": int(r.get("rpm_limit") or 60),
        "tpmLimit": int(r.get("tpm_limit") or 60000),
        "createdAt": str(r.get("created_at", "")),
        "updatedAt": str(r.get("updated_at", "")),
    }


def _usage_row(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": r["id"],
        "day": str(r.get("day") or ""),
        "totalRequests": int(r.get("total_requests") or 0),
        "totalTokens": int(r.get("total_tokens") or 0),
        "cost": float(r.get("cost") or 0),
        "peakRpm": int(r.get("peak_rpm") or 0),
    }
