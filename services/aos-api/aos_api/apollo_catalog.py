"""Apollo Channel / Spoke catalog — scheme 66 (metadata; Full runtime deferred)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.apollo_catalog")

CHANNEL_ORDER = ("dev", "staging", "stable")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS apollo_channel (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  rank INT NOT NULL DEFAULT 0,
  promoted_from TEXT,
  promoted_at TIMESTAMPTZ,
  recalled_from TEXT,
  recalled_at TIMESTAMPTZ,
  meta JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS apollo_spoke (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'lite',
  channel_id TEXT NOT NULL REFERENCES apollo_channel(id),
  version TEXT NOT NULL DEFAULT '0.3.0-dev',
  status TEXT NOT NULL DEFAULT 'online',
  heartbeat_ok BOOLEAN NOT NULL DEFAULT TRUE,
  hub TEXT NOT NULL DEFAULT 'dev-hub',
  runtime TEXT NOT NULL DEFAULT 'compose',
  meta JSONB NOT NULL DEFAULT '{}'::jsonb
);
"""


def ensure_schema(conn=None) -> None:
    def _run(c):
        c.execute(SCHEMA_SQL)

    if conn is None:
        with connect() as c:
            _run(c)
            c.commit()
    else:
        _run(conn)


def ensure_seed(conn=None) -> None:
    """Idempotent Channel + Spoke seeds."""
    ensure_schema(conn)

    def _run(c):
        channels = [
            ("dev", "Dev", 0),
            ("staging", "Staging", 1),
            ("stable", "Stable", 2),
        ]
        for cid, name, rank in channels:
            c.execute(
                """
                INSERT INTO apollo_channel (id, name, status, rank)
                VALUES (%s, %s, 'open', %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (cid, name, rank),
            )
        spokes = [
            (
                "spoke-local-dev",
                "Local Lite Spoke",
                "lite",
                "dev",
                "0.3.0-dev",
                "online",
                True,
                "compose",
            ),
            (
                "spoke-full-stub",
                "Full Spoke (deferred runtime)",
                "full",
                "staging",
                "0.3.0-dev",
                "planned",
                False,
                "deferred",
            ),
        ]
        for row in spokes:
            c.execute(
                """
                INSERT INTO apollo_spoke
                  (id, name, kind, channel_id, version, status, heartbeat_ok, runtime)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO NOTHING
                """,
                row,
            )
        log.info("apollo_catalog_seed_ensured channels=%s spokes=%s", len(channels), len(spokes))

    if conn is None:
        with connect() as c:
            _run(c)
            c.commit()
    else:
        _run(conn)


def _channel_row(r: Any) -> dict[str, Any]:
    return {
        "id": r["id"],
        "name": r["name"],
        "status": r["status"],
        "rank": int(r["rank"]),
        "promotedFrom": r["promoted_from"],
        "promotedAt": r["promoted_at"].isoformat() if r["promoted_at"] else None,
        "recalledFrom": r["recalled_from"],
        "recalledAt": r["recalled_at"].isoformat() if r["recalled_at"] else None,
        "meta": r["meta"] if isinstance(r["meta"], dict) else (r["meta"] or {}),
    }


def _spoke_row(r: Any) -> dict[str, Any]:
    return {
        "id": r["id"],
        "name": r["name"],
        "kind": r["kind"],
        "mode": r["kind"],
        "channel": r["channel_id"],
        "channelId": r["channel_id"],
        "version": r["version"],
        "status": r["status"],
        "heartbeatOk": bool(r["heartbeat_ok"]),
        "hub": r["hub"],
        "runtime": r["runtime"],
        "meta": r["meta"] if isinstance(r["meta"], dict) else (r["meta"] or {}),
    }


def list_channels() -> list[dict[str, Any]]:
    ensure_seed()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM apollo_channel ORDER BY rank, id"
        ).fetchall()
    return [_channel_row(r) for r in rows]


def get_channel(channel_id: str) -> dict[str, Any]:
    ensure_seed()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM apollo_channel WHERE id=%s", (channel_id,)
        ).fetchone()
    if not row:
        raise ApiError(code="NOT_FOUND", message="channel missing", status_code=404)
    return _channel_row(row)


def _next_channel(cid: str) -> str | None:
    try:
        i = CHANNEL_ORDER.index(cid)
    except ValueError:
        return None
    if i + 1 >= len(CHANNEL_ORDER):
        return None
    return CHANNEL_ORDER[i + 1]


def _prev_channel(cid: str) -> str | None:
    try:
        i = CHANNEL_ORDER.index(cid)
    except ValueError:
        return None
    if i <= 0:
        return None
    return CHANNEL_ORDER[i - 1]


def promote_channel(channel_id: str) -> dict[str, Any]:
    """Promote channel pointer: move spoke bindings? Scheme: advance channel record identity.

    Minimal semantics: the named channel is the *source*; promote creates/updates
    the next-rank channel's promoted_from marker and returns both. Spokes on this
    channel optionally stay; we mark meta.lastPromote.
    """
    ensure_seed()
    nxt = _next_channel(channel_id)
    if not nxt:
        raise ApiError(
            code="CHANNEL_PROMOTE_BLOCKED",
            message=f"channel {channel_id} has no promote target",
            status_code=400,
        )
    now = datetime.now(timezone.utc)
    with connect() as conn:
        src = conn.execute(
            "SELECT * FROM apollo_channel WHERE id=%s", (channel_id,)
        ).fetchone()
        if not src:
            raise ApiError(code="NOT_FOUND", message="channel missing", status_code=404)
        if src["status"] != "open":
            raise ApiError(
                code="CHANNEL_PROMOTE_BLOCKED",
                message="channel not open",
                status_code=400,
            )
        conn.execute(
            """
            UPDATE apollo_channel
            SET promoted_from=%s, promoted_at=%s,
                meta = COALESCE(meta, '{}'::jsonb) || %s::jsonb
            WHERE id=%s
            """,
            (
                channel_id,
                now,
                json.dumps({"lastPromoteFrom": channel_id}),
                nxt,
            ),
        )
        # Move lite spokes forward for demo catalog (full stub stays until explicit)
        conn.execute(
            """
            UPDATE apollo_spoke
            SET channel_id=%s
            WHERE channel_id=%s AND kind='lite'
            """,
            (nxt, channel_id),
        )
        conn.commit()
        dst = conn.execute(
            "SELECT * FROM apollo_channel WHERE id=%s", (nxt,)
        ).fetchone()
    log.info("channel_promote from=%s to=%s", channel_id, nxt)
    return {
        "ok": True,
        "from": channel_id,
        "to": nxt,
        "channel": _channel_row(dst),
    }


def recall_channel(channel_id: str) -> dict[str, Any]:
    ensure_seed()
    prev = _prev_channel(channel_id)
    if not prev:
        raise ApiError(
            code="CHANNEL_RECALL_BLOCKED",
            message=f"channel {channel_id} has no recall target",
            status_code=400,
        )
    now = datetime.now(timezone.utc)
    with connect() as conn:
        src = conn.execute(
            "SELECT * FROM apollo_channel WHERE id=%s", (channel_id,)
        ).fetchone()
        if not src:
            raise ApiError(code="NOT_FOUND", message="channel missing", status_code=404)
        conn.execute(
            """
            UPDATE apollo_channel
            SET recalled_from=%s, recalled_at=%s,
                meta = COALESCE(meta, '{}'::jsonb) || %s::jsonb
            WHERE id=%s
            """,
            (
                channel_id,
                now,
                json.dumps({"lastRecallFrom": channel_id}),
                prev,
            ),
        )
        conn.execute(
            """
            UPDATE apollo_spoke
            SET channel_id=%s
            WHERE channel_id=%s AND kind='lite'
            """,
            (prev, channel_id),
        )
        conn.commit()
        dst = conn.execute(
            "SELECT * FROM apollo_channel WHERE id=%s", (prev,)
        ).fetchone()
    log.info("channel_recall from=%s to=%s", channel_id, prev)
    return {
        "ok": True,
        "from": channel_id,
        "to": prev,
        "channel": _channel_row(dst),
    }


def list_spokes() -> list[dict[str, Any]]:
    ensure_seed()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM apollo_spoke ORDER BY id"
        ).fetchall()
    return [_spoke_row(r) for r in rows]


def get_spoke(spoke_id: str) -> dict[str, Any]:
    ensure_seed()
    aliases = {
        "local": "spoke-local-dev",
        "dev": "spoke-local-dev",
        "lite": "spoke-local-dev",
    }
    sid = aliases.get(spoke_id, spoke_id)
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM apollo_spoke WHERE id=%s", (sid,)
        ).fetchone()
    if not row:
        raise ApiError(code="NOT_FOUND", message="spoke missing", status_code=404)
    out = _spoke_row(row)
    if spoke_id != sid:
        out["requestedId"] = spoke_id
    return out


def fleet_payload() -> dict[str, Any]:
    ensure_seed()
    spokes = list_spokes()
    channels = list_channels()
    return {
        "hub": {
            "id": "dev-hub",
            "mode": "lite",
            "status": "online",
            "channelCatalogReady": True,
            "fullSpokeRuntimeDeferred": True,
        },
        "spokes": spokes,
        "channels": [
            {"id": c["id"], "name": c["name"], "status": c["status"], "rank": c["rank"]}
            for c in channels
        ],
    }
