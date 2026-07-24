"""184m — TTL / forget archive jobs (lifecycle soft-archive)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Any

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.retention")

# Core types: archive OK, forgotten forbidden
FORGET_DENY = frozenset({"WorkOrder", "Site", "Organization", "Project"})

LIFECYCLE_DDL = """
CREATE TABLE IF NOT EXISTS object_lifecycle (
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  reason TEXT NOT NULL DEFAULT '',
  archived_at TIMESTAMPTZ,
  ttl_days INT,
  org_id TEXT NOT NULL DEFAULT 'dev-org',
  project_id TEXT NOT NULL DEFAULT 'dev-project',
  meta JSONB NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (object_type, object_id)
);
"""


def ensure_lifecycle_schema(conn=None) -> None:
    from aos_api.db import connect

    def _run(c) -> None:
        c.execute(LIFECYCLE_DDL)

    if conn is None:
        with connect() as c:
            _run(c)
            c.commit()
    else:
        _run(conn)


def ttl_days_default() -> int:
    try:
        return max(1, int(os.getenv("AOS_RETENTION_TTL_DAYS") or "90"))
    except ValueError:
        return 90


def dry_run() -> bool:
    return (os.getenv("AOS_RETENTION_DRY_RUN") or "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    s = str(raw).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _props_dict(props: Any) -> dict[str, Any]:
    if isinstance(props, dict):
        return props
    if isinstance(props, str):
        try:
            out = json.loads(props)
            return out if isinstance(out, dict) else {}
        except Exception:
            return {}
    return {}


def list_candidates(*, limit: int = 200) -> list[dict[str, Any]]:
    """Objects eligible for archive by TTL / Insight heuristic."""
    from aos_api.db import connect

    ensure_lifecycle_schema()
    ttl = ttl_days_default()
    cutoff = datetime.now(timezone.utc) - timedelta(days=ttl)
    out: list[dict[str, Any]] = []
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT o.object_type, o.object_id, o.props, t.created_at AS type_created
            FROM obj_instance o
            LEFT JOIN meta_object_type t ON t.id = o.object_type
            ORDER BY o.object_type, o.object_id
            LIMIT 5000
            """
        ).fetchall()
        existing = {
            (r["object_type"], r["object_id"]): r["status"]
            for r in conn.execute(
                "SELECT object_type, object_id, status FROM object_lifecycle"
            ).fetchall()
        }
    for r in rows:
        ot, oid = r["object_type"], r["object_id"]
        st = existing.get((ot, oid), "active")
        if st in {"archived", "forgotten"}:
            continue
        props = _props_dict(r["props"])
        life = props.get("lifecycle") if isinstance(props.get("lifecycle"), dict) else {}
        obj_ttl = life.get("ttlDays")
        try:
            use_ttl = int(obj_ttl) if obj_ttl is not None else ttl
        except (TypeError, ValueError):
            use_ttl = ttl
        # eligibility: Insight* types OR explicit lifecycle.ttlDays OR props.retentionCandidate
        is_insight = "insight" in str(ot).lower()
        explicit = obj_ttl is not None or bool(props.get("retentionCandidate"))
        if not (is_insight or explicit):
            continue
        ts = (
            _parse_ts(life.get("updatedAt"))
            or _parse_ts(props.get("updatedAt"))
            or _parse_ts(props.get("createdAt"))
            or _parse_ts(r.get("type_created"))
        )
        if ts is None:
            # no timestamp: treat as candidate only if retentionCandidate forced
            if not props.get("retentionCandidate") and not explicit:
                continue
            ts = datetime.now(timezone.utc) - timedelta(days=use_ttl + 1)
        age_cutoff = datetime.now(timezone.utc) - timedelta(days=use_ttl)
        if ts > age_cutoff:
            continue
        out.append(
            {
                "objectType": ot,
                "objectId": oid,
                "ttlDays": use_ttl,
                "refTs": ts.isoformat(),
                "reason": "ttl_expired",
            }
        )
        if len(out) >= limit:
            break
    _ = cutoff  # documented policy window
    return out


def archive_one(
    conn,
    *,
    object_type: str,
    object_id: str,
    reason: str,
    ttl: int,
    status: str = "archived",
) -> None:
    if status == "forgotten" and object_type in FORGET_DENY:
        raise ValueError(f"forgotten forbidden for core type {object_type}")
    now = datetime.now(timezone.utc)
    conn.execute(
        """
        INSERT INTO object_lifecycle (
          object_type, object_id, status, reason, archived_at, ttl_days, meta
        ) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)
        ON CONFLICT (object_type, object_id) DO UPDATE SET
          status=EXCLUDED.status,
          reason=EXCLUDED.reason,
          archived_at=EXCLUDED.archived_at,
          ttl_days=EXCLUDED.ttl_days,
          meta=EXCLUDED.meta
        """,
        (
            object_type,
            object_id,
            status,
            reason,
            now,
            ttl,
            json.dumps({"source": "184m"}),
        ),
    )


def run_retention(*, force_dry: bool | None = None) -> dict[str, Any]:
    from aos_api.db import connect

    ensure_lifecycle_schema()
    is_dry = dry_run() if force_dry is None else force_dry
    cands = list_candidates()
    archived = 0
    skipped = 0
    errors: list[str] = []
    if is_dry:
        return {
            "ok": True,
            "dryRun": True,
            "candidates": len(cands),
            "archived": 0,
            "items": cands[:50],
        }
    with connect() as conn:
        for c in cands:
            try:
                archive_one(
                    conn,
                    object_type=c["objectType"],
                    object_id=c["objectId"],
                    reason=c["reason"],
                    ttl=int(c["ttlDays"]),
                    status="archived",
                )
                archived += 1
            except Exception as exc:
                skipped += 1
                errors.append(f"{c['objectType']}/{c['objectId']}:{exc}")
        conn.commit()
    log.info("retention_run archived=%s candidates=%s dry=%s", archived, len(cands), is_dry)
    return {
        "ok": True,
        "dryRun": False,
        "candidates": len(cands),
        "archived": archived,
        "skipped": skipped,
        "errors": errors[:20],
    }


def count_archived() -> int:
    from aos_api.db import connect

    try:
        ensure_lifecycle_schema()
        with connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM object_lifecycle WHERE status='archived'"
            ).fetchone()
            return int(row["c"] if row else 0)
    except Exception as exc:
        log.warning("retention_count_skip err=%s", exc)
        return 0


def count_active_candidates() -> int:
    try:
        return len(list_candidates(limit=500))
    except Exception as exc:
        log.warning("retention_candidates_skip err=%s", exc)
        return 0
