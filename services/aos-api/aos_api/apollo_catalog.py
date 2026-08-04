"""Apollo Channel / Spoke catalog — scheme 66 + Full Spoke MVP (158 helm-mock)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.tenant_scope import TenantScope, apply_transaction_scope

log = get_logger("aos-api.apollo_catalog")

CHANNEL_ORDER = ("dev", "staging", "stable")
FULL_SPOKE_ID = "spoke-full-stub"

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
  org_id TEXT NOT NULL DEFAULT 'dev-org',
  meta JSONB NOT NULL DEFAULT '{}'::jsonb
);
"""


def ensure_schema(conn=None) -> None:
    """Compatibility hook; Apollo DDL is owned by Alembic after TI-4 A1."""
    _ = conn


def ensure_seed(conn=None) -> None:
    """Idempotent Channel + Spoke seeds."""
    ensure_schema(conn)

    def _run(c):
        channels = [
            ("dev", "Dev", 0),
            ("staging", "Staging", 1),
            ("stable", "Stable", 2),
            ("hotfix", "Hotfix", 90),
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
                "dev-org",
                "dev-project",
            ),
            (
                "spoke-full-stub",
                "Full Spoke (helm-mock)",
                "full",
                "staging",
                "0.3.0-dev",
                "planned",
                False,
                "deferred",
                "dev-org",
                "dev-project",
            ),
        ]
        apply_transaction_scope(c, TenantScope("dev-org", "dev-project"))
        for row in spokes:
            c.execute(
                """
                INSERT INTO apollo_spoke
                  (id, name, kind, channel_id, version, status, heartbeat_ok,
                   runtime, org_id, project_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (org_id,project_id,id) DO NOTHING
                """,
                row,
            )
        log.info("apollo_catalog_seed_ensured channels=%s spokes=%s", len(channels), len(spokes))
        _apply_full_spoke_mode(c)
        c.execute("RESET ROLE")

    if conn is None:
        with connect() as c:
            _run(c)
            c.commit()
    else:
        _run(conn)


def full_spoke_mode() -> str:
    """mock|compose|kind|off — default mock (158). kind = doc-only for now."""
    raw = (os.environ.get("AOS_FULL_SPOKE_MODE") or "mock").strip().lower()
    if raw in {"off", "0", "false", "deferred"}:
        return "off"
    if raw in {"kind", "k8s", "helm"}:
        return "kind"
    if raw in {"compose"}:
        return "compose"
    return "mock"


def full_spoke_mock_ready() -> bool:
    return full_spoke_mode() != "off"


def _apply_full_spoke_mode(c) -> None:
    """When MODE≠off, promote Full stub to helm-mock; MODE=off keeps/restores deferred."""
    if not full_spoke_mock_ready():
        c.execute(
            """
            UPDATE apollo_spoke
            SET name=%s, runtime='deferred', status='planned', heartbeat_ok=FALSE,
                meta = COALESCE(meta, '{}'::jsonb) || %s::jsonb
            WHERE id=%s AND kind='full'
            """,
            (
                "Full Spoke (deferred runtime)",
                json.dumps({"fullSpokeMode": "off", "scheme": "158"}),
                FULL_SPOKE_ID,
            ),
        )
        return
    runtime = "helm-mock" if full_spoke_mode() in {"mock", "compose"} else "helm-kind-pending"
    status = "online" if full_spoke_mode() in {"mock", "compose"} else "planned"
    hb = full_spoke_mode() in {"mock", "compose"}
    name = (
        "Full Spoke (helm-mock)"
        if full_spoke_mode() in {"mock", "compose"}
        else "Full Spoke (kind pending)"
    )
    c.execute(
        """
        UPDATE apollo_spoke
        SET name=%s, runtime=%s, status=%s, heartbeat_ok=%s,
            meta = COALESCE(meta, '{}'::jsonb) || %s::jsonb
        WHERE id=%s AND kind='full'
        """,
        (
            name,
            runtime,
            status,
            hb,
            json.dumps(
                {
                    "fullSpokeMode": full_spoke_mode(),
                    "scheme": "158",
                    "note": "helm-mock MVP; true kind/k8s still deferred",
                }
            ),
            FULL_SPOKE_ID,
        ),
    )


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
    try:
        org_id = r["org_id"]
    except Exception:  # noqa: BLE001
        org_id = "dev-org"
    try:
        project_id = r["project_id"]
    except Exception:  # noqa: BLE001
        project_id = "dev-project"
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
        "orgId": org_id or "dev-org",
        "projectId": project_id or "dev-project",
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


def promote_channel(scope: TenantScope, channel_id: str) -> dict[str, Any]:
    """Promote channel pointer with health + asset gates (scheme 160).

    Minimal semantics: the named channel is the *source*; promote creates/updates
    the next-rank channel's promoted_from marker and returns both. Spokes on this
    channel optionally stay; we mark meta.lastPromote.
    """
    ensure_seed()
    if channel_id == "hotfix":
        raise ApiError(
            code="CHANNEL_PROMOTE_BLOCKED",
            message="hotfix is a side channel; use Change merge-stable stub",
            status_code=400,
        )
    nxt = _next_channel(channel_id)
    if not nxt:
        raise ApiError(
            code="CHANNEL_PROMOTE_BLOCKED",
            message=f"channel {channel_id} has no promote target",
            status_code=400,
        )
    # 160 · asset compatibleChannels gate (target = nxt)
    from aos_api.apollo_ops import assert_promote_assets_ok

    assert_promote_assets_ok(nxt)

    now = datetime.now(timezone.utc)
    with connect(scope) as conn:
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
        # 160 · health gate on lite spokes currently on source channel
        unhealthy = conn.execute(
            """
            SELECT id, heartbeat_ok FROM apollo_spoke
            WHERE channel_id=%s AND kind='lite' AND heartbeat_ok=FALSE
            """,
            (channel_id,),
        ).fetchall()
        if unhealthy:
            ids = [r["id"] for r in unhealthy]
            raise ApiError(
                code="CHANNEL_PROMOTE_UNHEALTHY",
                message=f"spoke health failed: {', '.join(ids)}",
                status_code=400,
                details={"spokeIds": ids},
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
                json.dumps({"lastPromoteFrom": channel_id, "scheme": "160"}),
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
        "scheme": "160",
    }


def recall_channel(scope: TenantScope, channel_id: str) -> dict[str, Any]:
    ensure_seed()
    prev = _prev_channel(channel_id)
    if not prev:
        raise ApiError(
            code="CHANNEL_RECALL_BLOCKED",
            message=f"channel {channel_id} has no recall target",
            status_code=400,
        )
    now = datetime.now(timezone.utc)
    with connect(scope) as conn:
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


def filter_spokes_by_scope(
    items: list[dict[str, Any]], scope: TenantScope
) -> list[dict[str, Any]]:
    """Data-plane spokes must not cross organization or workspace."""
    return [
        item
        for item in items
        if (item.get("orgId"), item.get("projectId")) == scope.key
    ]


def list_spokes(scope: TenantScope) -> list[dict[str, Any]]:
    ensure_seed()
    with connect(scope) as conn:
        rows = conn.execute(
            "SELECT * FROM apollo_spoke ORDER BY id"
        ).fetchall()
    items = [_spoke_row(r) for r in rows]
    return filter_spokes_by_scope(items, scope)


def get_spoke(scope: TenantScope, spoke_id: str) -> dict[str, Any]:
    ensure_seed()
    aliases = {
        "local": "spoke-local-dev",
        "dev": "spoke-local-dev",
        "lite": "spoke-local-dev",
        "full": FULL_SPOKE_ID,
    }
    sid = aliases.get(spoke_id, spoke_id)
    with connect(scope) as conn:
        row = conn.execute(
            "SELECT * FROM apollo_spoke WHERE id=%s", (sid,)
        ).fetchone()
    if not row:
        raise ApiError(code="NOT_FOUND", message="spoke missing", status_code=404)
    out = _spoke_row(row)
    if spoke_id != sid:
        out["requestedId"] = spoke_id
    return out


def record_spoke_heartbeat(
    scope: TenantScope,
    spoke_id: str,
    *,
    ok: bool = True,
) -> dict[str, Any]:
    """158 · Spoke heartbeat (Lite or Full). Org-scoped."""
    ensure_seed()
    spoke = get_spoke(scope, spoke_id)
    now = datetime.now(timezone.utc)
    with connect(scope) as conn:
        conn.execute(
            """
            UPDATE apollo_spoke
            SET heartbeat_ok=%s, status=%s,
                meta = COALESCE(meta, '{}'::jsonb) || %s::jsonb
            WHERE org_id=%s AND project_id=%s AND id=%s
            """,
            (
                bool(ok),
                "online" if ok else "degraded",
                json.dumps({"lastHeartbeatAt": now.isoformat()}),
                *scope.key,
                spoke["id"],
            ),
        )
        conn.commit()
    return get_spoke(scope, spoke["id"])


def apply_full_spoke_plan(
    scope: TenantScope,
    spoke_id: str,
    *,
    plan_id: str | None = None,
) -> dict[str, Any]:
    """158 · Mock Helm apply — records Reported State; no cluster mutate."""
    ensure_seed()
    spoke = get_spoke(scope, spoke_id)
    if spoke.get("kind") != "full":
        raise ApiError(
            code="SPOKE_NOT_FULL",
            message="apply-plan is for kind=full only",
            status_code=400,
        )
    if not full_spoke_mock_ready() and spoke.get("runtime") == "deferred":
        raise ApiError(
            code="FULL_SPOKE_DEFERRED",
            message="set AOS_FULL_SPOKE_MODE=mock (default) to enable helm-mock",
            status_code=503,
        )
    now = datetime.now(timezone.utc)
    pid = plan_id or f"plan-{now.strftime('%Y%m%d%H%M%S')}"
    reported = {
        "lastPlanId": pid,
        "lastApplyAt": now.isoformat(),
        "applyMode": full_spoke_mode(),
        "chart": "aos-spoke-full",
        "reportedState": "Applied(mock)",
        "scheme": "158",
    }
    with connect(scope) as conn:
        conn.execute(
            """
            UPDATE apollo_spoke
            SET status='online', heartbeat_ok=TRUE,
                runtime=CASE WHEN runtime='deferred' THEN 'helm-mock' ELSE runtime END,
                meta = COALESCE(meta, '{}'::jsonb) || %s::jsonb
            WHERE org_id=%s AND project_id=%s AND id=%s
            """,
            (json.dumps(reported), *scope.key, spoke["id"]),
        )
        conn.commit()
    out = get_spoke(scope, spoke["id"])
    return {"ok": True, "planId": pid, "spoke": out, "reported": reported}


def full_spoke_plan_artifact() -> dict[str, Any]:
    """Metadata for chart stub (no helm binary required)."""
    return {
        "chart": "aos-spoke-full",
        "path": "deploy/spoke-full/chart",
        "version": "0.1.0",
        "appVersion": "0.3.0-dev",
        "renderScript": "scripts/ci/helm-template-spoke-full.sh",
        "mode": full_spoke_mode(),
        "mockReady": full_spoke_mock_ready(),
        "k8sDeferred": True,
        "scheme": "158",
    }


def fleet_payload(scope: TenantScope) -> dict[str, Any]:
    ensure_seed()
    spokes = list_spokes(scope)
    channels = list_channels()
    mock_ready = full_spoke_mock_ready()
    from aos_api.apollo_ops import ops_hub_flags

    hub = {
        "id": "dev-hub",
        "mode": "lite",
        "status": "online",
        "channelCatalogReady": True,
        # true K8s/kind fleet still deferred; mock MVP is separate
        "fullSpokeRuntimeDeferred": True,
        "fullSpokeMockReady": mock_ready,
        "fullSpokeMode": full_spoke_mode(),
        **ops_hub_flags(),
    }
    return {
        "hub": hub,
        "spokes": spokes,
        "channels": [
            {"id": c["id"], "name": c["name"], "status": c["status"], "rank": c["rank"]}
            for c in channels
        ],
    }
