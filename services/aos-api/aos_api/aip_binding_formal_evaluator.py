"""Formal capability-binding evaluator: current health transaction consumer.

This module is the single place the full eight-dependency binding evaluator reads
Provider Health. It must be called inside a single native transaction that has
already established the tenant scope (``aos.org_id`` / ``aos.project_id``) and
acquired the health epoch fence via :func:`aos_provider_health_epoch_lock` with
``p_shared=true``. The fence guarantees that a concurrent health observation
committed after this snapshot forces a serialization failure (40001) at
commit time instead of certifying a stale ``healthy`` status.

The helper is intentionally fail-closed: a missing, future-dated, expired, or
ambiguous latest observation raises rather than returning a permissive default.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ProviderHealthFactUnavailable(RuntimeError):
    """Raised when current health cannot be established fail-closed."""


@dataclass(frozen=True)
class ProviderHealthFact:
    epoch: int
    observation_id: str
    provider_ref: Dict[str, Any]
    status: str
    availability_pct: Optional[int]
    p50_latency_ms: Optional[int]
    observed_at: datetime
    expires_at: Optional[datetime]


def _utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


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
    org, project = scope.key
    asset_id = provider_ref.get("assetId")
    if not asset_id:
        raise ProviderHealthFactUnavailable("PROVIDER_HEALTH_REF_MISSING_ASSET_ID")

    epoch_row = conn.execute(
        "SELECT public.aos_provider_health_epoch_lock(%s,%s,%s::jsonb,true)",
        (org, project, json.dumps(provider_ref, sort_keys=True)),
    ).fetchone()
    if epoch_row is None:
        raise ProviderHealthFactUnavailable("PROVIDER_HEALTH_EPOCH_LOCK_FAILED")
    epoch = int(epoch_row[0])

    rows = conn.execute(
        """SELECT observation_id, provider_ref, status, availability_pct, p50_latency_ms,
                  observed_at, expires_at
           FROM public.aip_provider_health_observation
           WHERE org_id=%s AND project_id=%s AND provider_ref->>'assetId'=%s
           ORDER BY observed_at DESC, observation_id DESC""",
        (org, project, asset_id),
    ).fetchall()
    if not rows:
        raise ProviderHealthFactUnavailable("PROVIDER_HEALTH_MISSING")

    latest = rows[0]
    # Two observations sharing the newest observed_at make "latest" ambiguous.
    if len(rows) > 1 and rows[1]["observed_at"] == latest["observed_at"]:
        raise ProviderHealthFactUnavailable("PROVIDER_HEALTH_AMBIGUOUS_LATEST")

    now = datetime.now(timezone.utc)
    observed_at = _utc(latest["observed_at"])
    if observed_at is None:
        raise ProviderHealthFactUnavailable("PROVIDER_HEALTH_OBSERVED_AT_INVALID")
    if observed_at > now:
        raise ProviderHealthFactUnavailable("PROVIDER_HEALTH_FUTURE_OBSERVATION")

    expires_at = _utc(latest["expires_at"])
    if expires_at is not None and expires_at <= now:
        raise ProviderHealthFactUnavailable("PROVIDER_HEALTH_EXPIRED")

    return ProviderHealthFact(
        epoch=epoch,
        observation_id=latest["observation_id"],
        provider_ref=provider_ref,
        status=latest["status"],
        availability_pct=latest["availability_pct"],
        p50_latency_ms=latest["p50_latency_ms"],
        observed_at=observed_at,
        expires_at=expires_at,
    )
