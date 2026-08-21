"""W-T7: Action tools must go through Draft/HITL — never fake write success."""

from __future__ import annotations

from typing import Any

ACTION_CLOSE_ID = "action.close"
ACTION_BLOCKED_REASON = (
    "Action 写回必须经 HITL→Draft/Approval/Receipt；工具面板禁止直接写成功（W-T7）"
)


def list_action_tool_exits() -> list[dict[str, Any]]:
    return [
        {
            "id": ACTION_CLOSE_ID,
            "kind": "Action",
            "name": "关闭/写回（HITL）",
            "requiresDraft": True,
            "blocked": True,
            "blockedReason": ACTION_BLOCKED_REASON,
        }
    ]


def invoke_action_tool(tool_id: str, *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    _ = payload
    return {
        "toolId": tool_id,
        "ok": False,
        "blocked": True,
        "kind": "Action",
        "requiresDraft": True,
        "result": {"message": ACTION_BLOCKED_REASON},
    }
