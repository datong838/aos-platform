"""Widget plugin registry — scheme 98 · 对齐 20 §3.1 / T08 §4."""
from __future__ import annotations

from typing import Any

from aos_api import plugin_disk

KEY = "widget_plugin_installs"
SUBDIR = "widgets"
DEFAULTS = (
    # ── 原有 9 个内置 plugin ──
    "filter-list",
    "object-table",
    "buddy-chip",
    "object-view",
    "page-header",
    "stat-card",
    "filter-bar",
    "detail-drawer",
    "trend-chart",
    # ── Layout 容器 ──
    "page-layout",
    "horizontal-grid",
    # ── 图表类（视觉稿新增）──
    "bar-chart",
    "pie-chart",
    "network-graph",
    "geo-map",
    # ── AI / 协作（Buddy 智能助手）──
    "chat-aside",
    "message-log",
    "chat-input",
    "context-chips",
    "assist-popover",
    # ── 数据展示 ──
    "wiki-card",
    "drill-panel",
    "status-badge",
    # ── 时间 / 事件 ──
    "timeline",
    "event-stream",
    # ── 操作 ──
    "button-group",
    # ── 扩展组件（视觉稿未用到）──
    "kanban",
    "gantt",
    "calendar",
)


def list_widget_plugins() -> dict[str, Any]:
    return plugin_disk.list_domain(
        SUBDIR,
        KEY,
        defaults=DEFAULTS,
        required=DEFAULTS,
        extra_fields=("canvasKind", "palette"),
    )


def install_plugin(plugin_id: str) -> dict[str, Any]:
    return plugin_disk.install(SUBDIR, KEY, plugin_id, DEFAULTS)


def uninstall_plugin(plugin_id: str) -> dict[str, Any]:
    return plugin_disk.uninstall(
        SUBDIR, KEY, plugin_id, defaults=DEFAULTS, required=DEFAULTS
    )


def palette_items() -> list[dict[str, Any]]:
    """Canvas 可挂调色板：已安装且 palette!=false 且有 canvasKind（含 stub）。"""
    items = []
    for it in list_widget_plugins().get("items") or []:
        if not it.get("installed"):
            continue
        if it.get("palette") is False:
            continue
        kind = it.get("canvasKind")
        if not kind:
            continue
        items.append(
            {
                "id": it["id"],
                "pluginId": it["id"],
                "kind": kind,
                "label": f"+ {it.get('nameZh') or it.get('name') or it['id']}",
                "nameZh": it.get("nameZh"),
                "runtime": it.get("runtime") or "inproc",
                "stub": kind == "stub" or (it.get("runtime") == "stub"),
            }
        )
    return items
