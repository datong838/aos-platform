"""Native formal evaluator facts; complete command remains under construction.

Health uses the original provider-ID shared epoch fence. It blocks concurrent
writers while held and preserves PostgreSQL 40001 on snapshot conflicts. Latest
exact observations and database time are required; this reader grants no start
permission and performs no provider call.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import psycopg
from psycopg import IsolationLevel
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row
from pydantic import ValidationError

from aos_api.aip_binding_evaluator_connection import EVALUATOR_LOGIN
from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
from aos_api.tenant_scope import TenantScope


class ProviderHealthFactUnavailable(RuntimeError):
    """Raised when current health cannot be established fail-closed."""


@dataclass(frozen=True)
class ProviderHealthFact:
    epoch: int
    observation_id: str
    provider_ref: Dict[str, Any]
    status: str
    availability_pct: Optional[float]
    p50_latency_ms: Optional[int]
    observed_at: datetime
    expires_at: datetime
    checked_at: datetime


def _require_health_consumer_transaction(conn: Any, scope: TenantScope) -> None:
    if (not isinstance(conn, psycopg.Connection) or type(scope) is not TenantScope
            or scope.key != ('org-org', 'dev-project') or conn.autocommit or conn.read_only
            or conn.isolation_level != IsolationLevel.SERIALIZABLE
            or conn.row_factory is not dict_row
            or conn.info.transaction_status != TransactionStatus.INTRANS):
        raise ProviderHealthFactUnavailable('PROVIDER_HEALTH_NATIVE_EVALUATOR_TRANSACTION_REQUIRED')
    row = conn.execute("""SELECT session_user AS login,current_user AS role,
        current_setting('aos.org_id',true) AS org,current_setting('aos.project_id',true) AS project,
        r.rolcanlogin,r.rolinherit,r.rolsuper,r.rolbypassrls,r.rolcreatedb,r.rolcreaterole,r.rolreplication,
        EXISTS(SELECT 1 FROM pg_auth_members m WHERE m.member=r.oid OR m.roleid=r.oid) AS membership
        FROM pg_roles r WHERE r.rolname=session_user""").fetchone()
    if (row is None or (row['login'], row['role']) != (EVALUATOR_LOGIN, EVALUATOR_LOGIN)
            or (row['org'], row['project']) != scope.key or not row['rolcanlogin']
            or any(row[name] for name in ('rolinherit', 'rolsuper', 'rolbypassrls',
                        'rolcreatedb', 'rolcreaterole', 'rolreplication', 'membership'))):
        raise ProviderHealthFactUnavailable('PROVIDER_HEALTH_EVALUATOR_IDENTITY_REQUIRED')


def read_current_provider_health_fact(
    conn: Any,
    scope: Any,
    provider_ref: Dict[str, Any],
) -> ProviderHealthFact:
    """Read the current Provider Health fact for an exact provider.

    Must run inside a transaction whose tenant scope is already set. Acquires a
    shared health epoch fence lock first, then reads the latest observation with
    fail-closed guards. Raises :class:`ProviderHealthFactUnavailable` on any
    condition that would otherwise let a stale or ambiguous observation through.
    """
    _require_health_consumer_transaction(conn, scope)
    try:
        exact = FormalExactRef.model_validate(provider_ref)
    except (ValidationError, TypeError, ValueError):
        raise ProviderHealthFactUnavailable('PROVIDER_HEALTH_EXACT_REF_REQUIRED') from None
    if exact.asset_type != 'ProviderInstanceRevision':
        raise ProviderHealthFactUnavailable('PROVIDER_HEALTH_EXACT_REF_REQUIRED')
    provider_ref = exact.model_dump(mode='json', by_alias=True)
    org, project = scope.key
    asset_id = exact.asset_id

    epoch_row = conn.execute(
        "SELECT public.aos_provider_health_epoch_lock(%s,%s,%s::jsonb,true) AS epoch",
        (org, project, json.dumps(provider_ref, sort_keys=True)),
    ).fetchone()
    if epoch_row is None:
        raise ProviderHealthFactUnavailable("PROVIDER_HEALTH_EPOCH_LOCK_FAILED")
    epoch = int(epoch_row["epoch"])

    rows = conn.execute(
        """SELECT observation_id, provider_ref, status, availability_pct, p50_latency_ms,
                  observed_at, expires_at
           FROM public.aip_provider_health_observation
           WHERE org_id=%s AND project_id=%s AND provider_ref->>'assetId'=%s
           ORDER BY observed_at DESC, observation_id DESC LIMIT 2""",
        (org, project, asset_id),
    ).fetchall()
    if not rows:
        raise ProviderHealthFactUnavailable("PROVIDER_HEALTH_MISSING")

    latest = rows[0]
    # Two observations sharing the newest observed_at make "latest" ambiguous.
    if len(rows) > 1 and rows[1]["observed_at"] == latest["observed_at"]:
        raise ProviderHealthFactUnavailable("PROVIDER_HEALTH_AMBIGUOUS_LATEST")

    if latest['provider_ref'] != provider_ref:
        raise ProviderHealthFactUnavailable('PROVIDER_HEALTH_LATEST_EXACT_REF_MISMATCH')
    now = conn.execute('SELECT clock_timestamp() AS checked_at').fetchone()['checked_at']
    observed_at, expires_at = latest['observed_at'], latest['expires_at']
    if any(not isinstance(value, datetime) or value.utcoffset() is None
           for value in (now, observed_at, expires_at)):
        raise ProviderHealthFactUnavailable('PROVIDER_HEALTH_AWARE_TIME_REQUIRED')
    if observed_at > now:
        raise ProviderHealthFactUnavailable('PROVIDER_HEALTH_FUTURE_OBSERVATION')
    if not observed_at <= now < expires_at:
        raise ProviderHealthFactUnavailable('PROVIDER_HEALTH_EXPIRED')
    if latest['status'] not in {'healthy', 'degraded', 'unavailable', 'unknown'}:
        raise ProviderHealthFactUnavailable('PROVIDER_HEALTH_STATUS_INVALID')

    return ProviderHealthFact(
        epoch=epoch,
        observation_id=latest["observation_id"],
        provider_ref=provider_ref,
        status=latest["status"],
        availability_pct=latest["availability_pct"],
        p50_latency_ms=latest["p50_latency_ms"],
        observed_at=observed_at,
        expires_at=expires_at,
        checked_at=now,
    )
