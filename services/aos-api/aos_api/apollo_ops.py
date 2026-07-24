"""Apollo ops deepening — scheme 160 (Change workflow · asset bind · ≠ 158 helm-mock)."""
from __future__ import annotations

import time
import uuid
from typing import Any

from aos_api.aip_kv_store import get_payload, put_payload
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.apollo_ops")

KEY_CHANGES = "apollo_ops_changes"
KEY_ASSETS = "apollo_ops_assets"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def list_changes(limit: int = 50) -> list[dict[str, Any]]:
    stored = get_payload(KEY_CHANGES) or {}
    items = stored.get("items")
    rows = list(items) if isinstance(items, list) else []
    rows.sort(key=lambda x: str(x.get("createdAt") or ""), reverse=True)
    return rows[: max(1, min(200, int(limit)))]


def _save_changes(items: list[dict[str, Any]]) -> None:
    put_payload(KEY_CHANGES, {"items": items})


def create_change(
    *,
    title: str,
    kind: str = "channel",
    channelId: str | None = None,
    summary: str | None = None,
    subject: str,
    org_id: str,
    project_id: str,
    emergency: bool = False,
) -> dict[str, Any]:
    kind_n = (kind or "channel").strip().lower()
    if kind_n not in {"channel", "hotfix", "config"}:
        raise ApiError(code="VALIDATION", message="kind must be channel|hotfix|config", status_code=400)
    if kind_n == "hotfix":
        emergency = True
        channelId = channelId or "hotfix"
    items = list_changes(limit=500)
    cid = f"chg-{uuid.uuid4().hex[:10]}"
    row = {
        "id": cid,
        "title": (title or "").strip() or cid,
        "kind": kind_n,
        "channelId": channelId,
        "summary": (summary or "").strip() or None,
        "status": "pending",
        "emergency": bool(emergency),
        "createdAt": _now(),
        "createdBy": subject,
        "orgId": org_id,
        "projectId": project_id,
        "decidedAt": None,
        "decidedBy": None,
        "decisionNote": None,
        "mergedToStableAt": None,
        "scheme": "160",
    }
    items.append(row)
    _save_changes(items)
    log.info("apollo_change_created id=%s kind=%s", cid, kind_n)
    return row


def _get_change(change_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    items = list_changes(limit=500)
    hit = next((x for x in items if x.get("id") == change_id), None)
    if not hit:
        raise ApiError(code="NOT_FOUND", message="change missing", status_code=404)
    return hit, items


def decide_change(
    change_id: str,
    *,
    approve: bool,
    subject: str,
    note: str | None = None,
) -> dict[str, Any]:
    hit, items = _get_change(change_id)
    if hit.get("status") != "pending":
        raise ApiError(code="CHANGE_NOT_PENDING", message="change not pending", status_code=400)
    hit["status"] = "approved" if approve else "rejected"
    hit["decidedAt"] = _now()
    hit["decidedBy"] = subject
    hit["decisionNote"] = (note or "").strip() or None
    _save_changes(items)
    log.info("apollo_change_decided id=%s status=%s", change_id, hit["status"])
    return hit


def merge_hotfix_to_stable(change_id: str, *, subject: str) -> dict[str, Any]:
    hit, items = _get_change(change_id)
    if hit.get("kind") != "hotfix":
        raise ApiError(code="CHANGE_NOT_HOTFIX", message="merge-stable only for hotfix", status_code=400)
    if hit.get("status") != "approved":
        raise ApiError(code="CHANGE_NOT_APPROVED", message="approve hotfix first", status_code=400)
    hit["mergedToStableAt"] = _now()
    hit["mergedBy"] = subject
    hit["status"] = "merged"
    _save_changes(items)
    return hit


def list_assets(limit: int = 50) -> list[dict[str, Any]]:
    stored = get_payload(KEY_ASSETS) or {}
    items = stored.get("items")
    rows = list(items) if isinstance(items, list) else []
    rows.sort(key=lambda x: str(x.get("createdAt") or ""), reverse=True)
    return rows[: max(1, min(200, int(limit)))]


def register_asset(
    *,
    contents: list[str] | None,
    hotfix: bool,
    compatible_channels: list[str] | None,
    subject: str,
) -> dict[str, Any]:
    items = list_assets(limit=500)
    aid = f"ab-{uuid.uuid4().hex[:8]}"
    channels = [str(c).strip() for c in (compatible_channels or ["dev", "staging", "stable"]) if str(c).strip()]
    if not channels:
        channels = ["dev", "staging", "stable"]
    row = {
        "bundleId": aid,
        "platformVersion": "0.3.0-dev",
        "contents": list(contents or ["WorkOrder", "CloseWorkOrder"]),
        "hotfix": bool(hotfix),
        "compatibleChannels": channels,
        "validated": True,
        "createdAt": _now(),
        "createdBy": subject,
        "scheme": "160",
    }
    items.append(row)
    put_payload(KEY_ASSETS, {"items": items})
    return row


def assert_promote_assets_ok(target_channel: str) -> None:
    """T09 A4 · reject promote when an asset forbids the target channel."""
    for asset in list_assets(limit=200):
        allowed = asset.get("compatibleChannels") or []
        if not isinstance(allowed, list):
            continue
        if target_channel not in [str(x) for x in allowed]:
            raise ApiError(
                code="CHANNEL_PROMOTE_ASSET",
                message=(
                    f"asset {asset.get('bundleId')} incompatible with channel {target_channel}; "
                    f"compatible={allowed}"
                ),
                status_code=400,
                details={"bundleId": asset.get("bundleId"), "compatibleChannels": allowed},
            )


def ops_hub_flags() -> dict[str, Any]:
    return {
        "apolloOpsDeepeningReady": True,
        "apolloOpsScheme": "160",
        "apolloOpsNote": "Change+health-gate+hotfix MVP · not multi-fleet · not Argo=Apollo",
    }
