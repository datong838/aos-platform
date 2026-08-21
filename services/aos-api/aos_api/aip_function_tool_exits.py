"""W-T6: Function tools must bind published Logic — block demo fn.echo fake-green."""

from __future__ import annotations

from typing import Any

from aos_api.tenant_scope import TenantScope

FN_ECHO_ID = "fn.echo"
FN_ECHO_BLOCKED_REASON = (
    "fn.echo 为演示 Function，非 published Logic exact；未挂已发布 Logic 不可用（W-T6）"
)


def list_function_tool_exits(
    scope: TenantScope,
    *,
    graphs: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Return Function catalog cards: blocked echo + published Logic exits."""
    items: list[dict[str, Any]] = [
        {
            "id": FN_ECHO_ID,
            "kind": "Function",
            "name": "Echo（演示）",
            "blocked": True,
            "blockedReason": FN_ECHO_BLOCKED_REASON,
            "requiresPublishedLogic": True,
        }
    ]
    for snap in graphs or []:
        published = int(getattr(snap, "published_version", 0) or 0)
        if published <= 0:
            continue
        graph_id = str(getattr(snap, "id", None) or getattr(snap, "graph_id", "") or "")
        if not graph_id:
            continue
        name = str(getattr(snap, "name", "") or graph_id)
        items.append(
            {
                "id": f"fn.logic.{graph_id}",
                "kind": "Function",
                "name": name,
                "logicGraphId": graph_id,
                "publishedVersion": published,
                "revision": int(getattr(snap, "revision", 0) or 0),
                "blocked": False,
                "blockedReason": "",
                "requiresPublishedLogic": True,
            }
        )
    _ = scope
    return items


def invoke_function_tool(tool_id: str, *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    _ = payload
    if tool_id == FN_ECHO_ID:
        return {
            "toolId": tool_id,
            "ok": False,
            "blocked": True,
            "kind": "Function",
            "result": {"message": FN_ECHO_BLOCKED_REASON},
        }
    if tool_id.startswith("fn.logic."):
        return {
            "toolId": tool_id,
            "ok": False,
            "blocked": True,
            "kind": "Function",
            "result": {
                "message": "已识别 published Logic 出口，执行门尚未接到工具面板试跑（诚实禁用假绿）",
            },
        }
    return {
        "toolId": tool_id,
        "ok": False,
        "blocked": True,
        "kind": "Function",
        "result": {"message": "未知 Function；仅允许 published Logic exact"},
    }
