"""W-T4: ten ecommerce Capability → tools panel exits (honest blocked projection)."""

from __future__ import annotations

from typing import Any

from aos_api.aip_solution_pack_publisher import CAPABILITY_IDS
from aos_api.tenant_scope import TenantScope

CAPABILITY_NAME_ZH: dict[str, str] = {
    "material.collect": "素材采集",
    "strategy.plan": "策略规划",
    "copy.generate": "文案生成",
    "script.compose": "脚本撰写",
    "speech.synthesize": "语音合成",
    "video.compose": "视频合成",
    "content.review": "内容审核",
    "live.orchestrate": "直播编排",
    "platform.adapt": "平台适配",
    "performance.review": "数据复盘",
}


def tool_id_for_capability(capability_id: str) -> str:
    return f"cap.{capability_id}"


def capability_id_from_tool(tool_id: str) -> str | None:
    if not tool_id.startswith("cap."):
        return None
    cid = tool_id[4:]
    return cid if cid in CAPABILITY_NAME_ZH else None


def list_capability_tool_exits(
    scope: TenantScope,
    *,
    bindings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return exactly ten Capability tool cards for the tools catalog."""
    _ = scope
    by_cap: dict[str, dict[str, Any]] = {}
    for raw in bindings or []:
        cap = raw.get("capability") or {}
        cid = str(cap.get("assetId") or raw.get("capabilityId") or "").strip()
        if cid:
            by_cap[cid] = raw

    items: list[dict[str, Any]] = []
    for cid in CAPABILITY_IDS:
        binding = by_cap.get(cid)
        blocked, reason = _blocked_reason(cid, binding)
        if not blocked:
            # W-T4: even healthy Binding cannot fake platform proxy invoke success.
            blocked = True
            reason = "专业能力代调门尚未接通生产 invoke；禁止假成功（W-T4）"
        items.append(
            {
                "id": tool_id_for_capability(cid),
                "kind": "Capability",
                "capabilityId": cid,
                "name": CAPABILITY_NAME_ZH.get(cid, cid),
                "nameZh": CAPABILITY_NAME_ZH.get(cid, cid),
                "blocked": blocked,
                "blockedReason": reason,
                "bindingId": (binding or {}).get("bindingId"),
                "health": (binding or {}).get("health"),
                "status": (binding or {}).get("status"),
            }
        )
    return items


def invoke_capability_tool(
    tool_id: str,
    *,
    binding: dict[str, Any] | None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Platform proxy gate: never fake GREEN invoke for Capability tools."""
    _ = payload
    cid = capability_id_from_tool(tool_id)
    if not cid:
        return {
            "toolId": tool_id,
            "ok": False,
            "blocked": True,
            "kind": "Capability",
            "result": {"message": "未知专业能力工具"},
        }
    blocked, reason = _blocked_reason(cid, binding)
    if blocked:
        return {
            "toolId": tool_id,
            "ok": False,
            "blocked": True,
            "kind": "Capability",
            "capabilityId": cid,
            "result": {"message": reason},
        }
    # Even when Binding looks ready, production proxy invoke is not wired in W-T4.
    return {
        "toolId": tool_id,
        "ok": False,
        "blocked": True,
        "kind": "Capability",
        "capabilityId": cid,
        "result": {
            "message": "专业能力代调门尚未接通生产 invoke；已禁止假成功（W-T4）",
        },
    }


def _blocked_reason(capability_id: str, binding: dict[str, Any] | None) -> tuple[bool, str]:
    name = CAPABILITY_NAME_ZH.get(capability_id, capability_id)
    if not binding:
        return True, f"「{name}」无组织 Binding，专业能力代调不可用"
    status = str(binding.get("status") or "").strip().lower()
    health = str(binding.get("health") or "").strip().lower()
    if status and status not in {"active", "ready", "bound"}:
        return True, f"「{name}」Binding 状态为 {status}，暂不可代调"
    if health in {"", "unknown", "unhealthy", "stale", "failed"}:
        return True, f"「{name}」Health={health or 'unknown'}，暂不可代调"
    if health not in {"healthy", "ok", "ready"}:
        return True, f"「{name}」Health={health}，暂不可代调"
    return False, ""
