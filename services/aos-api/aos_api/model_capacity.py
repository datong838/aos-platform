"""Phase 2 · Model Capacity — rate limits + daily usage.

capacity_limits: per-org / per-project / per-user rate limits (rpm/tpm).
capacity_usage: daily aggregated metrics (requests, tokens, cost, peak_rpm).
"""
from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.model_capacity")

_DEFAULT_ORG = "dev-org"
_DEFAULT_PROJECT = "dev-project"

# Scope constants
SCOPE_PROJECT = "project"
SCOPE_USER = "user"


def ensure_schema() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS capacity_limits (
              id TEXT PRIMARY KEY,
              scope TEXT NOT NULL,
              scope_key TEXT NOT NULL DEFAULT '',
              rpm_limit INTEGER NOT NULL DEFAULT 60,
              tpm_limit INTEGER NOT NULL DEFAULT 60000,
              org_id TEXT NOT NULL DEFAULT 'dev-org',
              project_id TEXT NOT NULL DEFAULT 'dev-project',
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_capacity_limits_scope
            ON capacity_limits (org_id, project_id, scope, scope_key)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS capacity_usage (
              id TEXT PRIMARY KEY,
              day DATE NOT NULL,
              total_requests INTEGER NOT NULL DEFAULT 0,
              total_tokens BIGINT NOT NULL DEFAULT 0,
              cost NUMERIC(14,6) NOT NULL DEFAULT 0,
              peak_rpm INTEGER NOT NULL DEFAULT 0,
              org_id TEXT NOT NULL DEFAULT 'dev-org',
              project_id TEXT NOT NULL DEFAULT 'dev-project',
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_capacity_usage_day
            ON capacity_usage (org_id, project_id, day)
            """
        )
        conn.commit()


# ── Limits ──


def list_limits(scope: str, *, scope_key: str | None = None) -> list[dict[str, Any]]:
    ensure_schema()
    clauses = ["org_id=%s", "project_id=%s", "scope=%s"]
    params: list[Any] = [_DEFAULT_ORG, _DEFAULT_PROJECT, scope]
    if scope_key:
        clauses.append("scope_key=%s")
        params.append(scope_key)
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM capacity_limits WHERE "
            + " AND ".join(clauses)
            + " ORDER BY created_at",
            tuple(params),
        ).fetchall()
    return [_limit_row(r) for r in rows]


def get_limit(limit_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM capacity_limits WHERE id=%s AND org_id=%s AND project_id=%s",
            (limit_id, _DEFAULT_ORG, _DEFAULT_PROJECT),
        ).fetchone()
    return _limit_row(row) if row else None


def get_or_default_limit(scope: str, scope_key: str) -> dict[str, Any]:
    """Get limit by scope+key, falling back to defaults if not set."""
    items = list_limits(scope, scope_key=scope_key)
    if items:
        return items[0]
    return {
        "id": "",
        "scope": scope,
        "scopeKey": scope_key,
        "rpmLimit": 60,
        "tpmLimit": 60000,
    }


def upsert_limit(scope: str, scope_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_schema()
    with connect() as conn:
        existing = conn.execute(
            """
            SELECT id FROM capacity_limits
             WHERE org_id=%s AND project_id=%s AND scope=%s AND scope_key=%s
            """,
            (_DEFAULT_ORG, _DEFAULT_PROJECT, scope, scope_key),
        ).fetchone()
        lid = existing["id"] if existing else f"cl-{uuid.uuid4().hex[:8]}"
        conn.execute(
            """
            INSERT INTO capacity_limits (
                id, scope, scope_key, rpm_limit, tpm_limit, org_id, project_id
            ) VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
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
                _DEFAULT_ORG,
                _DEFAULT_PROJECT,
            ),
        )
        conn.commit()
    return get_limit(lid)  # type: ignore[return-value]


# ── Usage ──


def list_usage(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    ensure_schema()
    clauses = ["org_id=%s", "project_id=%s"]
    params: list[Any] = [_DEFAULT_ORG, _DEFAULT_PROJECT]
    if start_date:
        clauses.append("day>=%s")
        params.append(start_date)
    if end_date:
        clauses.append("day<=%s")
        params.append(end_date)
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM capacity_usage WHERE "
            + " AND ".join(clauses)
            + " ORDER BY day DESC LIMIT %s",
            tuple(params + [limit]),
        ).fetchall()
    return [_usage_row(r) for r in rows]


def upsert_usage(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_schema()
    uid = payload.get("id") or f"cu-{uuid.uuid4().hex[:8]}"
    with connect() as conn:
        existing = conn.execute(
            """
            SELECT id FROM capacity_usage
             WHERE org_id=%s AND project_id=%s AND day=%s
            """,
            (_DEFAULT_ORG, _DEFAULT_PROJECT, payload["day"]),
        ).fetchone()
        uid = existing["id"] if existing else uid
        conn.execute(
            """
            INSERT INTO capacity_usage (
                id, day, total_requests, total_tokens, cost, peak_rpm, org_id, project_id
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
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
                _DEFAULT_ORG,
                _DEFAULT_PROJECT,
            ),
        )
        conn.commit()
    return get_usage(uid)  # type: ignore[return-value]


def get_usage(usage_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM capacity_usage WHERE id=%s AND org_id=%s AND project_id=%s",
            (usage_id, _DEFAULT_ORG, _DEFAULT_PROJECT),
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
