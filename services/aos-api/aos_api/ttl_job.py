"""184m — Insight TTL / soft-archive job (no physical delete of core objects)."""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.ttl-job")

# id -> insight row
_INSIGHTS: dict[str, dict[str, Any]] = {}


def reset_insight_store() -> None:
    _INSIGHTS.clear()


def ttl_days() -> int:
    raw = (os.getenv("AOS_INSIGHT_TTL_DAYS") or "90").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 90


def upsert_insight(row: dict[str, Any]) -> dict[str, Any]:
    rid = str(row.get("id") or "")
    if not rid:
        raise ValueError("insight id required")
    now = datetime.now(timezone.utc).isoformat()
    prev = dict(_INSIGHTS.get(rid, {}))
    merged = {**prev, **row}
    merged.setdefault("status", "proposed")
    merged.setdefault("createdAt", now)
    merged.setdefault("lastRefAt", merged["createdAt"])
    merged["updatedAt"] = now
    _INSIGHTS[rid] = merged
    return dict(merged)


def list_insights(*, status: str | None = None) -> list[dict[str, Any]]:
    rows = list(_INSIGHTS.values())
    if status:
        rows = [r for r in rows if r.get("status") == status]
    return sorted(rows, key=lambda x: x.get("createdAt") or "", reverse=True)


def _parse_ts(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        # allow Z
        s = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return None


def candidates(*, now_ts: float | None = None) -> list[dict[str, Any]]:
    """Insights past TTL and not yet archived."""
    now = now_ts if now_ts is not None else time.time()
    cutoff = now - ttl_days() * 86400
    out: list[dict[str, Any]] = []
    for row in _INSIGHTS.values():
        if row.get("status") == "archived":
            continue
        ts = _parse_ts(str(row.get("lastRefAt") or row.get("createdAt") or ""))
        if ts is None:
            continue
        if ts <= cutoff:
            out.append(dict(row))
    return sorted(out, key=lambda x: x.get("createdAt") or "")


def run_archive(*, now_ts: float | None = None, dry_run: bool = False) -> dict[str, Any]:
    cand = candidates(now_ts=now_ts)
    archived: list[str] = []
    if not dry_run:
        for row in cand:
            rid = row["id"]
            stored = _INSIGHTS.get(rid)
            if not stored:
                continue
            stored["status"] = "archived"
            stored["archivedAt"] = datetime.now(timezone.utc).isoformat()
            stored["archiveReason"] = f"ttl_days>{ttl_days()}"
            archived.append(rid)
            # best-effort PG lifecycle mirror
            ot, oid = stored.get("objectType"), stored.get("objectId")
            if ot and oid:
                try:
                    from aos_api.db import connect
                    from aos_api.retention_jobs import archive_one, ensure_lifecycle_schema

                    ensure_lifecycle_schema()
                    with connect() as conn:
                        archive_one(
                            conn,
                            object_type=str(ot),
                            object_id=str(oid),
                            reason=stored["archiveReason"],
                            ttl=ttl_days(),
                            status="archived",
                        )
                        conn.commit()
                except Exception as exc:
                    log.warning("ttl_pg_lifecycle_skip err=%s", exc)
    # also run object retention pass
    obj_ret: dict[str, Any] = {}
    try:
        from aos_api.retention_jobs import run_retention

        obj_ret = run_retention(force_dry=dry_run)
    except Exception as exc:
        log.warning("retention_jobs_skip err=%s", exc)
        obj_ret = {"ok": False, "detail": str(exc)}
    log.info(
        "ttl_archive dry=%s candidates=%s archived=%s ttl_days=%s",
        dry_run,
        len(cand),
        len(archived),
        ttl_days(),
    )
    return {
        "ok": True,
        "ttlDays": ttl_days(),
        "dryRun": dry_run,
        "candidateCount": len(cand),
        "archivedCount": len(archived),
        "archivedIds": archived,
        "objectRetention": obj_ret,
        "candidates": [
            {
                "id": c["id"],
                "objectType": c.get("objectType"),
                "objectId": c.get("objectId"),
                "createdAt": c.get("createdAt"),
                "status": c.get("status"),
            }
            for c in cand[:50]
        ],
    }


def status_snapshot() -> dict[str, Any]:
    active = [r for r in _INSIGHTS.values() if r.get("status") != "archived"]
    archived = [r for r in _INSIGHTS.values() if r.get("status") == "archived"]
    cand = candidates()
    obj_cands = 0
    try:
        from aos_api.retention_jobs import count_active_candidates

        obj_cands = count_active_candidates()
    except Exception:
        obj_cands = 0
    return {
        "ttlDays": ttl_days(),
        "insightTotal": len(_INSIGHTS),
        "active": len(active),
        "archived": len(archived),
        "archiveCandidates": len(cand) + obj_cands,
        "insightCandidates": len(cand),
        "objectCandidates": obj_cands,
        "preview": [
            {"id": c["id"], "createdAt": c.get("createdAt"), "objectId": c.get("objectId")}
            for c in cand[:10]
        ],
    }
